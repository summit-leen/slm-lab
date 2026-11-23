# -*- coding: utf-8 -*-
"""把 align_diff 存下的 npz 画成 PNG（对比度拉伸），方便直接看差值区域。"""
from __future__ import annotations

import sys

import numpy as np
import wx

src = sys.argv[1] if len(sys.argv) > 1 else r"runs\diff_check.npz"
out = sys.argv[2] if len(sys.argv) > 2 else "diff_view.png"
lo_pct = float(sys.argv[3]) if len(sys.argv) > 3 else 2.0
hi_pct = float(sys.argv[4]) if len(sys.argv) > 4 else 98.0

d = np.load(src)
diff = d["diff"].astype(np.float32)
print("shape:", diff.shape, "min/max:", diff.min(), diff.max(), "mean:", diff.mean())

lo, hi = np.percentile(diff, lo_pct), np.percentile(diff, hi_pct)
print(f"stretch {lo:.1f} .. {hi:.1f}")
norm = np.clip((diff - lo) / max(hi - lo, 1e-6), 0, 1)
img8 = (norm * 255).astype(np.uint8)

hh, ww = img8.shape
rgb = np.repeat(img8[:, :, None], 3, axis=2)
wx.Image(ww, hh, rgb.tobytes()).SaveFile(out, wx.BITMAP_TYPE_PNG)
print("saved", out)

# 粗略分块均值，定位差值集中在哪
bh, bw = max(1, hh // 8), max(1, ww // 16)
print("\n分块均值 (白-黑):")
for y in range(0, hh - bh + 1, bh):
    row = []
    for x in range(0, ww - bw + 1, bw):
        row.append(f"{diff[y:y + bh, x:x + bw].mean():7.1f}")
    print(" ".join(row))
