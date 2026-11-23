# -*- coding: utf-8 -*-
"""焦距标定图案：同一面板上按列放不同焦距的透镜，一次拍摄就能看出相机
所在平面（面板后多少 mm）对应哪一列最聚焦。

    python code/lens_focal_sweep.py --show --hold 300     # 显示到 SLM
    python code/lens_focal_sweep.py --save captures/sweep # 只存图案

每列焦距相同、横向排开；相机拍一帧后，最亮（斑点最小）的那一列就说明
"相机传感器离面板的距离" ≈ 该列的 f。
"""
from __future__ import annotations

import argparse
import math
import os
import sys
import time
from types import SimpleNamespace

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from random_lens_array import Lens, build_pattern  # noqa: E402

W, H = 1024, 768
PITCH_UM = 18.0
LAM_NM = 620.0


def make_lenses(f_list, cols_x, rows_y):
    p = PITCH_UM * 1e-6
    lam = LAM_NM * 1e-9
    lenses = []
    for f_mm, cx in zip(f_list, cols_x):
        f = f_mm * 1e-3
        r_alias = lam * f / (2.0 * p) / p          # 单位：px
        r = min(0.85 * r_alias, 58.0)
        for cy in rows_y:
            lenses.append(Lens(cx, cy, r, f, p))
    return lenses


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--f", default="35,45,55,65,75", help="各列焦距 mm，逗号分隔")
    ap.add_argument("--pitch", type=float, default=104.0, help="列间距（面板 px）")
    ap.add_argument("--rows", type=int, default=3, help="每列几个透镜")
    ap.add_argument("--save", default="captures/sw_phase")
    ap.add_argument("--show", action="store_true")
    ap.add_argument("--hold", type=float, default=30.0)
    ap.add_argument("--monitor", type=int, default=1)
    args = ap.parse_args(argv)

    f_list = [float(x) for x in args.f.split(",")]
    n = len(f_list)
    x0 = W / 2.0 - (n - 1) * args.pitch / 2.0
    cols = [x0 + i * args.pitch for i in range(n)]
    rows = [H / 2.0 + (i - (args.rows - 1) / 2.0) * 140.0 for i in range(args.rows)]

    lenses = make_lenses(f_list, cols, rows)
    pargs = SimpleNamespace(pitch=PITCH_UM, lam=LAM_NM, sign=-1, tilt=(0.0, 0.0))
    gray = build_pattern(W, H, lenses, pargs)

    print(f"列焦距 mm: {f_list}")
    print(f"列中心 x : {[round(c, 1) for c in cols]}")
    for f_mm, cx in zip(f_list, cols):
        L = [l for l in lenses if abs(l.cx - cx) < 1e-6][0]
        print(f"  f={f_mm:4.0f} mm  r={L.r:4.1f} px  D={2*L.r*PITCH_UM/1000:.2f} mm  "
              f"环数={L.zones:.1f}")

    os.makedirs(os.path.dirname(os.path.abspath(args.save)), exist_ok=True)
    np.save(args.save + ".npy", gray)
    try:
        from PIL import Image
        Image.fromarray(gray).save(args.save + ".png")
    except Exception:
        pass
    print(f"已存 {args.save}.npy / .png  (灰度均值 {gray.mean():.1f})")

    if args.show:
        from slm_driver import SLM
        slm = SLM(monitor=args.monitor)
        w, h = slm.getSize()
        img = gray if (w, h) == (W, H) else np.zeros((h, w), np.uint8)
        slm.update(img)
        print(f"\n显示 {args.hold:g} s ...")
        sys.stdout.flush()
        slm.run(hold=args.hold)
        slm.close()
        globals()["_keep"] = slm
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
