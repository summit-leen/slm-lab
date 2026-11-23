# -*- coding: utf-8 -*-
"""逐像素的黑白差值判定：调制到底出现在画面哪个区域。

    python align_diff.py --cycles 6 --dwell 1.0

面板全黑 / 全白交替若干轮，相机分别累加两种状态的图，然后给出
    mean_black, mean_white, ratio
    max|diff| 及其像素位置
    |diff| 的 99 分位
    |diff| > 3% 满量程的像素占比
真的穿过液晶的光，只会在画面里的某一块区域产生差值（液晶区的像），
而不是全画面均匀的漂移。
"""
from __future__ import annotations

import argparse
import os
import sys
import threading
import time

import numpy as np

from psf_capture import Cam, auto_exposure
from slm_driver import SLM


def ascii_preview(img: np.ndarray, width: int = 64) -> str:
    h, w = img.shape
    step = max(1, w // width)
    rows = []
    chars = " .:-=+*#%@"
    lo, hi = float(img.min()), float(img.max())
    span = max(hi - lo, 1e-9)
    for y in range(0, h, max(1, step // 2 * 2)):
        line = "".join(
            chars[min(9, int((img[y, x] - lo) / span * 9))] for x in range(0, w, step)
        )
        rows.append(line)
    return "\n".join(rows)


def run(slm: SLM, args) -> None:
    w, h = slm.getSize()
    black = np.zeros((h, w), np.uint8)
    white = np.full((h, w), 255, np.uint8)

    slm.update(white)
    time.sleep(0.5)
    cam = Cam(args.exposure_us, args.gain, args.fps, args.bin, None)
    if args.exposure_us is None:
        print(f"自动曝光 -> {auto_exposure(cam, 0.5):.0f} us")
    print(f"相机 {cam.model} {cam.width}x{cam.height} bin={args.bin} "
          f"曝光 {cam.cam.ExposureTime.GetValue():.0f} us 满量程 {cam.full}")
    sys.stdout.flush()

    acc_b = acc_w = None
    for i in range(args.cycles):
        slm.update(black)
        time.sleep(args.dwell)
        b = cam.grab(args.frames).astype(np.float64)
        slm.update(white)
        time.sleep(args.dwell)
        wt = cam.grab(args.frames).astype(np.float64)
        acc_b = b if acc_b is None else acc_b + b
        acc_w = wt if acc_w is None else acc_w + wt
        print(f"  cycle {i + 1}/{args.cycles}: black={b.mean():8.1f} white={wt.mean():8.1f} "
              f"ratio={b.mean() / max(wt.mean(), 1e-9):.3f}")
        sys.stdout.flush()

    mb, mw = acc_b / args.cycles, acc_w / args.cycles
    diff = mw - mb                      # 白-黑
    fs = float(cam.full)
    ratio = float(mb.mean() / max(mw.mean(), 1e-9))
    ad = np.abs(diff)
    iy, ix = np.unravel_index(int(np.argmax(ad)), ad.shape)
    frac = float((ad > 0.03 * fs).mean())

    print("\n==== 汇总 ====")
    print(f"mean black = {mb.mean():.1f}   mean white = {mw.mean():.1f}   ratio = {ratio:.4f}")
    print(f"max |white-black| = {ad.max():.1f} 计数 ({ad.max() / fs * 100:.1f}% FS) at (x={ix}, y={iy})")
    print(f"|diff| 99 分位 = {np.percentile(ad, 99):.1f} 计数 ({np.percentile(ad, 99) / fs * 100:.2f}% FS)")
    print(f"|diff| > 3% FS 的像素占比 = {frac * 100:.2f}%")
    print("判据: max|diff| < 2% FS 且占比 < 1% → 这一位置没有调制")
    print("\n差值图（白-黑，归一化显示）:")
    print(ascii_preview(diff))

    if args.save:
        np.savez(args.save, black=mb, white=mw, diff=diff,
                 exposure=cam.cam.ExposureTime.GetValue(), full=fs)
        print(f"\n已存 {args.save}")

    cam.close()
    slm.close()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="黑白逐像素差值判定")
    ap.add_argument("--cycles", type=int, default=6)
    ap.add_argument("--dwell", type=float, default=1.0)
    ap.add_argument("--frames", type=int, default=3)
    ap.add_argument("--exposure-us", type=float, default=None)
    ap.add_argument("--gain", type=float, default=0.0)
    ap.add_argument("--fps", type=float, default=15.0)
    ap.add_argument("--bin", type=int, default=4)
    ap.add_argument("--monitor", type=int, default=1)
    ap.add_argument("--save", default=None)
    args = ap.parse_args(argv)

    slm = SLM(monitor=args.monitor, verbose=True)

    def _worker():
        try:
            run(slm, args)
        except BaseException as exc:
            print("采集失败:", repr(exc))
            sys.stdout.flush()
            try:
                slm.close()
            except Exception:
                pass

    threading.Thread(target=_worker, daemon=True).start()
    slm.run()
    sys.stdout.flush()
    os._exit(0)


if __name__ == "__main__":
    raise SystemExit(main())
