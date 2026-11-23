# -*- coding: utf-8 -*-
"""SLM 当菲涅尔透镜：一次拍两张（有透镜 / 平场）相减，得到实像。

为什么相减
----------
面板只调制约 8% 的光（无起偏器），其余 92% 直穿，在像面上是一层
被"散焦"的均匀底子。这张底子在两种图案下完全相同，减掉即可分离出
仅由透镜相位形成的实像。

几何（1/f = 1/d + 1/s）
-----------------------
物体放在 SLM 前 d，传感器放在 SLM 后 s，则像距 s 满足上式。
m = s/d 是放大率，物方视场 = 传感器尺寸 / m。
离轴倾斜 --tilt 决定像在传感器上的横移：Delta = q*lambda*s/p。

用法
----
    python lens_capture.py --f 600 --s 1200 --tilt 0.05 --out runs/lens1
    python lens_capture.py --f 400 --s 800  --tilt 0.06 --out runs/lens2 --exposure-us 20000
"""
from __future__ import annotations

import argparse
import os
import threading
import time

import numpy as np

from psf_capture import Cam, auto_exposure
from slm_driver import SLM
from slm_lens import build_lens


def _save_png(img: np.ndarray, path: str, lo_pct: float = 0.5, hi_pct: float = 99.5) -> None:
    import wx
    lo = np.percentile(img, lo_pct)
    hi = np.percentile(img, hi_pct)
    norm = np.clip((img - lo) / max(float(hi - lo), 1e-9), 0, 1)
    img8 = (norm * 255).astype(np.uint8)
    h, w = img8.shape
    rgb = np.repeat(img8[:, :, None], 3, axis=2)
    wx.Image(w, h, rgb.tobytes()).SaveFile(path, wx.BITMAP_TYPE_PNG)


def run(slm: SLM, args, w: int, h: int) -> None:
    os.makedirs(args.out, exist_ok=True)
    cam = Cam(args.exposure_us, args.gain, 10.0, binning=args.bin, roi=None)
    time.sleep(0.3)
    print(f"相机 {cam.model}, {cam.width}x{cam.height} bin={args.bin}")

    lens = build_lens(w, h, args.pitch, args.lam, args.f, args.gamma, -1,
                      tilt=(args.tilt, args.tilt_y))
    flat = np.full((h, w), 128, np.uint8)

    slm.update(lens)
    time.sleep(args.settle)
    if args.exposure_us is None:
        auto_exposure(cam)
    a = cam.grab(args.frames).astype(np.float32)
    print(f"[有透镜] mean={a.mean():.1f} max={a.max():.1f}")

    slm.update(flat)
    time.sleep(args.settle)
    b = cam.grab(args.frames).astype(np.float32)
    print(f"[平  场] mean={b.mean():.1f} max={b.max():.1f}")

    d = a - b
    print(f"[差  值] mean={d.mean():.2f} std={d.std():.2f} "
          f"min={d.min():.1f} max={d.max():.1f} "
          f"({100*max(abs(d.min()), abs(d.max()))/cam.full:.1f}% FS)")

    np.save(os.path.join(args.out, "lens.npy"), a)
    np.save(os.path.join(args.out, "flat.npy"), b)
    np.save(os.path.join(args.out, "diff.npy"), d)
    _save_png(a, os.path.join(args.out, "lens.png"))
    _save_png(d, os.path.join(args.out, "diff.png"))
    print("已保存 lens.npy / flat.npy / diff.npy / lens.png / diff.png 到", args.out)
    cam.close()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="SLM 透镜成像：有透镜 - 平场")
    ap.add_argument("--out", required=True)
    ap.add_argument("--f", type=float, default=600.0, help="焦距 mm")
    ap.add_argument("--s", type=float, default=None, help="SLM→传感器 mm（仅用于打印几何）")
    ap.add_argument("--tilt", type=float, default=0.05, help="离轴倾斜 周期/像素")
    ap.add_argument("--tilt-y", type=float, default=0.0)
    ap.add_argument("--pitch", type=float, default=18.0)
    ap.add_argument("--lam", type=float, default=620.0)
    ap.add_argument("--gamma", type=float, default=400.0)
    ap.add_argument("--exposure-us", type=float, default=None)
    ap.add_argument("--gain", type=float, default=0.0)
    ap.add_argument("--bin", type=int, default=4)
    ap.add_argument("--frames", type=int, default=8)
    ap.add_argument("--settle", type=float, default=0.3)
    args = ap.parse_args(argv)

    slm = SLM(monitor=1, verbose=True)
    w, h = slm.getSize()
    print(f"SLM {w}x{h}; f={args.f:g} mm, tilt={args.tilt:g} 周期/像素", flush=True)
    if args.s:
        lam, p = args.lam * 1e-9, args.pitch * 1e-6
        s_mm = args.s
        dx = args.tilt * lam * s_mm * 1e-3 / p * 1e3
        px = dx / (0.002 * args.bin)
        print(f"  预期像面横移 dx = {dx:.2f} mm ≈ {px:.0f} px 向右 (bin={args.bin})", flush=True)

    def _worker():
        try:
            run(slm, args, w, h)
        except BaseException as exc:
            print("采集失败:", repr(exc), flush=True)
        finally:
            slm.close()

    t = threading.Thread(target=_worker, daemon=True)
    t.start()
    slm.run()
    t.join(timeout=3.0)
    import sys
    sys.stdout.flush()
    os._exit(0)


if __name__ == "__main__":
    raise SystemExit(main())
