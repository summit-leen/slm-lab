# -*- coding: utf-8 -*-
"""把 stack.npy 里的一帧（或平均值）存成对比度拉伸后的 PNG。

    python view_stack.py runs\obj_c\stack.npy out.png [帧号|-1 表示平均]
"""
from __future__ import annotations

import sys

import numpy as np
import wx

path = sys.argv[1]
out = sys.argv[2]
idx = int(sys.argv[3]) if len(sys.argv) > 3 else -1

s = np.load(path).astype(np.float32)
if s.ndim == 3:
    img = s.mean(axis=0) if idx < 0 else s[idx]
else:
    img = s

print(f"{path}: shape {s.shape} -> 用 {'均值' if idx < 0 else f'第 {idx} 帧'}")
print(f"  min {img.min():.1f} max {img.max():.1f} mean {img.mean():.1f}")

lo, hi = np.percentile(img, 0.5), np.percentile(img, 99.5)
print(f"  拉伸 {lo:.1f} .. {hi:.1f}")
norm = np.clip((img - lo) / max(hi - lo, 1e-6), 0, 1)
img8 = (norm * 255).astype(np.uint8)
h, w = img8.shape
rgb = np.repeat(img8[:, :, None], 3, axis=2)
wx.Image(w, h, rgb.tobytes()).SaveFile(out, wx.BITMAP_TYPE_PNG)
print("  saved", out)
