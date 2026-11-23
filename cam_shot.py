# -*- coding: utf-8 -*-
"""抓一帧存成 PNG，方便人眼直接看相机到底拍到了什么。

    python cam_shot.py --grey 255 --out shot_white.png
    python cam_shot.py --grey 0   --out shot_black.png
"""
from __future__ import annotations

import argparse
import os
import sys
import threading
import time

import numpy as np

import wx

from psf_capture import Cam
from slm_driver import SLM


def shot(slm: SLM, args) -> None:
    w, h = slm.getSize()
    slm.update(np.full((h, w), args.grey, np.uint8))
    time.sleep(args.settle)

    cam = Cam(args.exposure_us, args.gain, args.fps, args.bin, None)
    frame = cam.grab(args.frames).astype(np.float32)
    full = float(cam.full)
    print(f"grey={args.grey} mean={frame.mean():.1f} max={frame.max():.0f} "
          f"min={frame.min():.0f} full={full:.0f} exposure={cam.cam.ExposureTime.GetValue():.0f}us",
          flush=True)

    norm = np.clip(frame / full, 0, 1)
    img8 = (norm * 255).astype(np.uint8)
    if args.gain_display > 1:
        img8 = np.clip(img8.astype(np.float32) * args.gain_display, 0, 255).astype(np.uint8)

    hh, ww = img8.shape
    rgb = np.repeat(img8[:, :, None], 3, axis=2)
    img = wx.Image(ww, hh, rgb.tobytes())
    img.SaveFile(args.out, wx.BITMAP_TYPE_PNG)
    print(f"已存 {args.out}  ({ww}x{hh})", flush=True)

    cam.close()
    slm.close()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--grey", type=int, default=255)
    ap.add_argument("--out", default="shot.png")
    ap.add_argument("--settle", type=float, default=0.5)
    ap.add_argument("--frames", type=int, default=5)
    ap.add_argument("--exposure-us", type=float, default=None)
    ap.add_argument("--gain", type=float, default=0.0)
    ap.add_argument("--fps", type=float, default=15.0)
    ap.add_argument("--bin", type=int, default=4)
    ap.add_argument("--monitor", type=int, default=1)
    ap.add_argument("--gain-display", type=float, default=1.0)
    args = ap.parse_args(argv)

    slm = SLM(monitor=args.monitor, verbose=True)

    def _worker():
        try:
            shot(slm, args)
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
