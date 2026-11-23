# -*- coding: utf-8 -*-
"""拍一组 PSF（每个编码掩模一张），供后续图像重建用。

一次运行做的事
--------------
1. 生成 N 个掩模（默认均匀随机相位），逐个显示到 SLM 屏；
2. 每个掩模稳定 ~0.12 s（约 7 个显示刷新周期）后，用 Basler 相机抓 K 帧取平均；
3. 期间可选先抓暗场（需要手动关光源）；
4. 结果写到 out_dir：
     meta.json           几何、曝光、相机、掩模参数
     masks/mask_XXX.npy  uint8 掩模（重建时要用的编码）
     psf/psf_XXX.npy     float32 平均图（已减暗场）
     dark.npy            暗场（如果抓了）
     stack.npy           所有 PSF 叠成的 (N, H, W) 数组，方便直接算

用法
----
    python psf_capture.py --auto --n 32 --out runs\\psf01
    python psf_capture.py --exposure-us 300 --n 32 --z-mm 15 --d-mm 300 --out runs\\psf02
    python psf_capture.py --n 1 --mask lens --focal 600 --out runs\\lens_psf

注意
----
* 相机此刻是过曝的（4.3 ms 全白），一定先用 --auto 或手动压曝光。
* 光源是连续 LED，曝光时间可以长；但掩模是静止的，所以不存在 60 Hz 混帧问题。
* 暗场必须在同样曝光下、关掉 LED 拍，否则减法没有意义。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import threading
import time
from datetime import datetime

import numpy as np
from pypylon import pylon

from slm_driver import SLM

# 面板标称：液晶延迟 Gamma = 400 nm，红光 620 nm -> alpha = 0.645 周期
# 相位 = 2*pi*alpha*gray/255，所以 pi 对应 gray = 255*0.5/alpha ≈ 198
PI_GRAY = int(round(255.0 * 0.5 / (400.0 / 620.0)))


def _parse_roi(text: str | None) -> tuple[int, int] | None:
    if not text:
        return None
    low = text.lower().replace(" ", "")
    if "x" not in low:
        raise SystemExit("--roi 需要形如 1200x800")
    w, h = low.split("x")[:2]
    return int(w), int(h)


# ---------------------------------------------------------------- 掩模生成
def make_masks(kind: str, n: int, width: int, height: int,
               focal_mm: float, seed: int) -> list[np.ndarray]:
    rng = np.random.default_rng(seed)
    out: list[np.ndarray] = []

    if kind == "random":
        for _ in range(n):
            out.append(rng.integers(0, 256, size=(height, width), dtype=np.uint8))
        return out

    if kind == "lens":
        yy, xx = np.mgrid[0:height, 0:width].astype(np.float64)
        cx, cy = (width - 1) / 2.0, (height - 1) / 2.0
        r2 = ((xx - cx) * 18e-6) ** 2 + ((yy - cy) * 18e-6) ** 2
        # 焦距按 0.7, 1.0, 1.4 ... 倍缩放，用来做 f 扫描
        for i in range(n):
            f = focal_mm * (0.7 ** (i % 3)) if n > 1 else focal_mm
            phi = -np.pi * r2 / (620e-9 * f * 1e-3)
            gray = np.rint(np.mod(phi, 2 * np.pi) / (2 * np.pi) * 255.0).astype(np.uint8)
            out.append(gray)
        return out

    if kind == "prism":
        # 锯齿相位光栅：周期 32/8/2 px → 偏折角 1.07/4.3/17 mrad
        yy, xx = np.mgrid[0:height, 0:width].astype(np.float64)
        periods = [32, 8, 2]
        for i in range(n):
            period = periods[i % len(periods)]
            phi = 2 * np.pi * ((xx % period) / period)
            gray = np.rint(phi / (2 * np.pi) * 255.0).astype(np.uint8)
            out.append(gray)
        return out

    if kind == "shutter":
        # 全黑 / 全白 交替：用来判定面板到底在不在光路里
        for i in range(n):
            v = 0 if i % 2 == 0 else 255
            out.append(np.full((height, width), v, np.uint8))
        return out

    if kind == "binary":
        # 二元随机相位 0/π：相位 = 2*pi*alpha*gray/255
        # alpha = Gamma/lambda = 400/620 = 0.645 -> 灰度 198 正好是 pi
        for _ in range(n):
            m = rng.random((height, width)) < 0.5
            out.append(np.where(m, PI_GRAY, 0).astype(np.uint8))
        return out

    if kind == "flat":
        for _ in range(n):
            out.append(np.full((height, width), 128, np.uint8))
        return out

    raise SystemExit(f"未知掩模类型 {kind}")


# ---------------------------------------------------------------- 相机
class Cam:
    def __init__(self, exposure_us: float | None, gain_db: float, fps: float,
                 binning: int = 1, roi: tuple[int, int] | None = None):
        tlf = pylon.TlFactory.GetInstance()
        devs = tlf.EnumerateDevices()
        if not devs:
            raise SystemExit("没找到 Basler 相机")
        self.cam = pylon.InstantCamera(tlf.CreateDevice(devs[0]))
        self.cam.Open()
        self.model = self.cam.GetDeviceInfo().GetModelName()
        for node, val in (("ExposureAuto", "Off"), ("GainAuto", "Off")):
            try:
                getattr(self.cam, node).SetValue(val)
            except Exception:
                pass
        self.cam.Gain.SetValue(gain_db)
        if exposure_us:
            self.cam.ExposureTime.SetValue(float(exposure_us))
        try:
            self.cam.AcquisitionFrameRateEnable.SetValue(True)
            self.cam.AcquisitionFrameRate.SetValue(float(fps))
        except Exception:
            pass
        try:
            self.cam.PixelFormat.SetValue("Mono12")
        except Exception:
            pass

        # 先 binning，再在缩小后的画布里开 ROI
        if binning and binning > 1:
            try:
                self.cam.BinningHorizontal.SetValue(int(binning))
                self.cam.BinningVertical.SetValue(int(binning))
            except Exception as exc:
                print("binning 失败，用软件 binning:", exc)
        if roi:
            w, h = roi
            w = min(int(w), self.cam.WidthMax.GetValue())
            h = min(int(h), self.cam.HeightMax.GetValue())
            x0 = ((self.cam.WidthMax.GetValue() - w) // 2) // 2 * 2
            y0 = ((self.cam.HeightMax.GetValue() - h) // 2) // 2 * 2
            try:
                # Basler 的顺序：先把 Width/Height 缩小，Offset 才有非零可用范围
                self.cam.Width.SetValue(w)
                self.cam.Height.SetValue(h)
                self.cam.OffsetX.SetValue(x0)
                self.cam.OffsetY.SetValue(y0)
            except Exception as exc:
                print("ROI 设置失败，用全画幅:", exc)

        self.conv = pylon.ImageFormatConverter()
        self.conv.OutputPixelFormat = pylon.PixelType_Mono16

        self.cam.StartGrabbing(pylon.GrabStrategy_LatestImageOnly)
        self.full = 4095 if "12" in self.cam.PixelFormat.GetValue() else 255
        self.binning = int(binning or 1)
        self.roi = tuple(roi) if roi else None
        self.width = int(self.cam.Width.GetValue())
        self.height = int(self.cam.Height.GetValue())

    def grab_one(self) -> np.ndarray:
        res = self.cam.RetrieveResult(5000, pylon.TimeoutHandling_ThrowException)
        try:
            if not res.GrabSucceeded():
                raise RuntimeError(res.GetErrorDescription())
            return self.conv.Convert(res).GetArray().copy()
        finally:
            res.Release()

    def grab(self, k: int) -> np.ndarray:
        acc = None
        for _ in range(k):
            img = self.grab_one().astype(np.float32)
            acc = img if acc is None else acc + img
        return acc / k

    def set_exposure(self, us: float) -> float:
        lo, hi = self.cam.ExposureTime.GetMin(), self.cam.ExposureTime.GetMax()
        us = float(min(max(us, lo), hi))
        self.cam.ExposureTime.SetValue(us)
        return us

    def close(self) -> None:
        try:
            self.cam.StopGrabbing()
            self.cam.Close()
        except Exception:
            pass


def auto_exposure(cam: Cam, target: float = 0.55, tries: int = 14) -> float:
    """二分曝光，让 99.9 分位亮度落在满量程 target 附近。"""
    us = cam.cam.ExposureTime.GetValue()
    best = us
    for _ in range(tries):
        cam.set_exposure(us)
        time.sleep(0.05)
        img = cam.grab(2)
        p = float(np.percentile(img, 99.9))
        ratio = p / (cam.full * target)
        print(f"  exposure {us:8.1f} us -> p99.9={p:7.1f} ({100*p/cam.full:5.1f}% FS)")
        if 0.75 <= ratio <= 1.35:
            best = us
            break
        best = us
        us = us / max(ratio, 0.05) ** 0.7
        if us < cam.cam.ExposureTime.GetMin():
            break
    cam.set_exposure(best)
    return best


# ---------------------------------------------------------------- 主流程
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="用 SLM 掩模 + Basler 相机拍 PSF 集")
    ap.add_argument("--out", required=True, help="输出目录")
    ap.add_argument("--n", type=int, default=32, help="掩模数量")
    ap.add_argument("--mask", default="random", choices=("random", "lens", "flat", "prism", "shutter", "binary"))
    ap.add_argument("--focal", type=float, default=600.0, help="lens 掩模的中心焦距 mm")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--frames", type=int, default=16, help="每个掩模平均帧数")
    ap.add_argument("--exposure-us", type=float, default=None)
    ap.add_argument("--gain", type=float, default=0.0)
    ap.add_argument("--fps", type=float, default=15.0)
    ap.add_argument("--auto", action="store_true", help="自动二分曝光")
    ap.add_argument("--settle", type=float, default=0.12, help="换图后等待秒数")
    ap.add_argument("--dark-frames", type=int, default=0,
                    help=">0 时先拍暗场（请先关掉光源）")
    ap.add_argument("--z-mm", type=float, default=40.0, help="SLM 到相机距离")
    ap.add_argument("--d-mm", type=float, default=40.0, help="针孔到 SLM 距离")
    ap.add_argument("--pinhole-um", type=float, default=None)
    ap.add_argument("--bin", type=int, default=4, help="相机 binning（4 表示 4x4，切 s=20mm 时零损失）")
    ap.add_argument("--roi", default=None, help="中心 ROI，形如 1200x800")
    ap.add_argument("--monitor", type=int, default=1)
    args = ap.parse_args(argv)

    out = os.path.abspath(args.out)
    for sub in ("", "masks", "psf"):
        os.makedirs(os.path.join(out, sub), exist_ok=True)

    slm = SLM(monitor=args.monitor, verbose=True)
    # wx 必须占用主线程：采集序列放工作线程，主线程跑事件循环
    def _worker():
        # 采集线程异常时必须主动关窗，否则主线程会永远卡在 MainLoop 里
        try:
            run_capture(slm, args, out)
        except BaseException as exc:
            print("采集失败:", repr(exc))
            sys.stdout.flush()
            try:
                slm.close()
            except Exception:
                pass

    t = threading.Thread(target=_worker, daemon=True)
    t.start()
    slm.run()
    print("事件循环结束")
    sys.stdout.flush()
    os._exit(0)


def run_capture(slm: SLM, args, out: str) -> None:
    W, H = slm.getSize()
    masks = make_masks(args.mask, args.n, W, H, args.focal, args.seed)
    print(f"SLM {W}x{H}, {len(masks)} 个 {args.mask} 掩模")

    cam = Cam(args.exposure_us, args.gain, args.fps, args.bin, _parse_roi(args.roi))
    print(f"相机 {cam.model}, {cam.width}x{cam.height} bin={cam.binning}, "
          f"满量程 {cam.full}, 曝光 {cam.cam.ExposureTime.GetValue():.0f} us")

    dark = None
    if args.dark_frames > 0:
        print(f"拍暗场 {args.dark_frames} 帧（光源应当已关闭）...")
        slm.update(masks[0])
        time.sleep(args.settle)
        dark = cam.grab(args.dark_frames)
        np.save(os.path.join(out, "dark.npy"), dark)
        print(f"  暗场均值 {dark.mean():.2f}")

    if args.auto or args.exposure_us is None:
        print("自动曝光（用第 0 个掩模）...")
        slm.update(masks[0])
        time.sleep(args.settle)
        us = auto_exposure(cam)
        print(f"  采用曝光 {us:.0f} us")
    else:
        us = cam.cam.ExposureTime.GetValue()

    psfs: list[np.ndarray] = []
    stats = []
    t0 = time.time()
    try:
        for i, mask in enumerate(masks):
            slm.update(mask)
            time.sleep(args.settle)
            img = cam.grab(args.frames)
            if dark is not None:
                img = img - dark
            np.save(os.path.join(out, "masks", f"mask_{i:03d}.npy"), mask)
            np.save(os.path.join(out, "psf", f"psf_{i:03d}.npy"), img.astype(np.float32))
            psfs.append(img.astype(np.float32))

            sat = float((img >= cam.full * 0.995).mean() * 100)
            yy, xx = np.mgrid[0:img.shape[0], 0:img.shape[1]]
            tot = img.sum()
            cy = float((img * yy).sum() / tot) if tot > 0 else float("nan")
            cx = float((img * xx).sum() / tot) if tot > 0 else float("nan")
            stats.append(dict(i=i, mean=float(img.mean()), max=float(img.max()),
                              sat_pct=sat, cx=cx, cy=cy, energy=float(tot)))
            print(f"[{i+1}/{len(masks)}] mean={img.mean():8.1f} max={img.max():7.0f} "
                  f"sat={sat:5.2f}% centroid=({cx:7.1f},{cy:7.1f})")
    finally:
        cam.close()

    stack = np.stack(psfs, axis=0)
    np.save(os.path.join(out, "stack.npy"), stack)

    meta = dict(
        created=datetime.now().isoformat(timespec="seconds"),
        slm=dict(width=W, height=H, monitor=args.monitor),
        camera=dict(model=cam.model, full_scale=cam.full, exposure_us=us,
                    gain_db=args.gain, fps=args.fps, frames_averaged=args.frames,
                    binning=cam.binning, roi=list(cam.roi) if cam.roi else None,
                    width=int(stack.shape[2]), height=int(stack.shape[1])),
        optics=dict(z_mm=args.z_mm, d_mm=args.d_mm, pinhole_um=args.pinhole_um,
                    wavelength_nm=620.0, slm_pitch_um=18.0),
        masks=dict(kind=args.mask, n=len(masks), seed=args.seed, focal_mm=args.focal),
        stats=stats,
        elapsed_s=round(time.time() - t0, 2),
    )
    with open(os.path.join(out, "meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    print(f"\n完成：{len(psfs)} 张 PSF, stack {stack.shape} -> {out}")
    print(f"耗时 {time.time()-t0:.1f} s")
    sys.stdout.flush()
    slm.close()


if __name__ == "__main__":
    raise SystemExit(main())
