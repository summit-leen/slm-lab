# -*- coding: utf-8 -*-
"""把任意 .npy 灰度数组原样显示在 SLM 上（不做任何缩放/插值）。

用于"把昨天采集用的那张掩模重新打出来"这类需求：图案一个像素都不改，
保证和标定/重建时看到的是同一张。

用法
----
    python slm_npy.py runs/e_bin/masks/mask_000.npy --hold 3600
    python slm_npy.py mask.npy --info            # 只看统计，不上屏
    python slm_npy.py mask.npy --hold 0          # 一直显示，Ctrl+C 结束
"""
from __future__ import annotations

import argparse
import os
import sys
import threading

import numpy as np


def describe(a: np.ndarray) -> None:
    print(f"数组 {a.shape} {a.dtype}, 灰度 {a.min()}..{a.max()}, 均值 {a.mean():.1f}")
    vals, counts = np.unique(a, return_counts=True)
    if len(vals) <= 6:
        total = a.size
        parts = [f"{v}:{c/total*100:.1f}%" for v, c in zip(vals, counts)]
        print("  " + ", ".join(parts))
    else:
        print(f"  {len(vals)} 个不同灰度值")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="显示 .npy 灰度图案")
    ap.add_argument("path", help=".npy 文件路径")
    ap.add_argument("--monitor", type=int, default=1)
    ap.add_argument("--hold", type=float, default=600.0, help="显示秒数，0=一直")
    ap.add_argument("--info", action="store_true", help="只打印统计")
    args = ap.parse_args(argv)

    a = np.load(args.path)
    if a.dtype != np.uint8:
        if a.dtype == np.bool_:
            a = a.astype(np.uint8) * 255
        else:
            lo, hi = float(a.min()), float(a.max())
            a = np.clip((a - lo) / max(hi - lo, 1e-12) * 255.0, 0, 255).astype(np.uint8)
            print(f"[提示] 非 uint8 输入，已线性拉伸到 0..255")
    if a.ndim != 2:
        raise SystemExit(f"需要二维数组，实际 {a.shape}")
    print(f"文件 {args.path}")
    describe(a)
    if args.info:
        return 0

    from slm_driver import SLM

    slm = SLM(monitor=args.monitor, verbose=False)
    w, h = slm.getSize()
    if a.shape != (h, w):
        raise SystemExit(f"尺寸不匹配：图案 {a.shape[::-1]} vs SLM {w}x{h}（不做缩放）")

    print(f"上屏 {w}x{h}")
    slm.update(a)

    if args.hold and args.hold > 0:
        def _timer():
            import time
            time.sleep(args.hold)
            print(f"{args.hold:g} s 到，关闭")
            sys.stdout.flush()
            slm.close()

        threading.Thread(target=_timer, daemon=True).start()
        print(f"显示 {args.hold:g} s ...")
    else:
        print("一直显示，Ctrl+C 结束")

    slm.run()
    print("结束")
    sys.stdout.flush()
    os._exit(0)


if __name__ == "__main__":
    raise SystemExit(main())
