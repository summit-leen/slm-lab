# -*- coding: utf-8 -*-
"""只读数、不改图案：用来做「遮住面板 → 看相机掉不掉」这类人工遮挡实验。

    python align_watch.py --hold 90 --grey 128

面板固定显示一个灰度（不闪），相机每 0.5 s 打一行
    t= 12.5   mean= 1419.3   max= 2898   (p99= 2701)
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


def watch(slm: SLM, args) -> None:
    w, h = slm.getSize()
    img = np.full((h, w), args.grey, np.uint8)
    slm.update(img)
    time.sleep(0.5)

    cam = Cam(args.exposure_us, args.gain, args.fps, args.bin, None)
    print(f"相机 {cam.model} {cam.width}x{cam.height} bin={args.bin} "
          f"曝光 {cam.cam.ExposureTime.GetValue():.0f} us 满量程 {cam.full}",
          flush=True)
    t0 = time.time()
    while time.time() - t0 < args.hold:
        f = cam.grab(1)
        print(f"t={time.time() - t0:6.1f}  mean={f.mean():8.1f}  max={f.max():6.0f}  "
              f"p99={np.percentile(f, 99):6.0f}", flush=True)
        time.sleep(max(0.0, args.period - 0.1))
    cam.close()
    slm.close()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--hold", type=float, default=90.0)
    ap.add_argument("--grey", type=int, default=128)
    ap.add_argument("--period", type=float, default=0.5)
    ap.add_argument("--exposure-us", type=float, default=None)
    ap.add_argument("--gain", type=float, default=0.0)
    ap.add_argument("--fps", type=float, default=15.0)
    ap.add_argument("--bin", type=int, default=4)
    ap.add_argument("--monitor", type=int, default=1)
    args = ap.parse_args(argv)

    slm = SLM(monitor=args.monitor, verbose=True)

    def _worker():
        try:
            watch(slm, args)
        except BaseException as exc:
            print("失败:", repr(exc), flush=True)
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
