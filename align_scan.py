# -*- coding: utf-8 -*-
"""光轴找正用的实时监视器：面板黑白交替，相机连续读数。

用法（先让用户盯着终端／或者事后看日志）：
    python align_scan.py --hold 90

它每 2 秒一个周期（1 s 全黑 + 1 s 全白），打印
    t= 12.4  black= 1850.2  white= 1861.0  ratio= 0.994
只有当光**真的穿过液晶像素**时 ratio 才会明显偏离 1（全黑那一秒应该暗很多）。
让面板缓慢平移/上下左右挪，看 ratio 什么时候塌下去，那就是对准了。
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


def scan(slm: SLM, args) -> None:
    w, h = slm.getSize()
    black = np.zeros((h, w), np.uint8)
    white = np.full((h, w), 255, np.uint8)

    slm.update(white)
    time.sleep(0.4)
    cam = Cam(args.exposure_us, args.gain, args.fps, args.bin, None)
    if args.exposure_us is None:
        us = auto_exposure(cam, 0.55)
        print(f"自动曝光 -> {us:.0f} us")
    print(f"相机 {cam.model}, {cam.width}x{cam.height} bin={args.bin}, "
          f"曝光 {cam.cam.ExposureTime.GetValue():.0f} us, 满量程 {cam.full}")
    sys.stdout.flush()

    t0 = time.time()
    best = (9.9, None)
    while time.time() - t0 < args.hold:
        slm.update(black)
        time.sleep(args.dwell)
        b = float(np.mean(cam.grab(args.frames)))
        slm.update(white)
        time.sleep(args.dwell)
        wt = float(np.mean(cam.grab(args.frames)))
        ratio = b / max(wt, 1e-9)
        print(f"t={time.time() - t0:6.1f}  black={b:8.1f}  white={wt:8.1f}  ratio={ratio:.3f}")
        sys.stdout.flush()
        if ratio < best[0]:
            best = (ratio, time.time() - t0)

    print(f"\n最小 ratio = {best[0]:.3f} (t={best[1]:.1f}s)。ratio < 0.6 才算光真的穿过像素。")
    sys.stdout.flush()
    cam.close()
    slm.close()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="黑白交替 + 相机读数，找光轴")
    ap.add_argument("--hold", type=float, default=90.0)
    ap.add_argument("--dwell", type=float, default=0.35, help="每种状态的停留秒数")
    ap.add_argument("--frames", type=int, default=2)
    ap.add_argument("--exposure-us", type=float, default=None)
    ap.add_argument("--gain", type=float, default=0.0)
    ap.add_argument("--fps", type=float, default=15.0)
    ap.add_argument("--bin", type=int, default=4)
    ap.add_argument("--monitor", type=int, default=1)
    args = ap.parse_args(argv)

    slm = SLM(monitor=args.monitor, verbose=True)

    def _worker():
        try:
            scan(slm, args)
        except BaseException as exc:
            print("扫描失败:", repr(exc))
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
