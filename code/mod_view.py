# -*- coding: utf-8 -*-
"""把 stack 的"跨掩模标准差"图存 PNG —— 这就是被 SLM 调制出来的那部分。

    python mod_view.py runs\obj_c\stack.npy out.png
"""
import sys

import numpy as np
import wx

src, out = sys.argv[1], sys.argv[2]
s = np.load(src).astype(np.float64)
sd = s.std(axis=0)
m = s.mean(axis=0)
print(f"{src}: std 中位 {np.median(sd):.2f}  最大 {sd.max():.1f}  "
      f"相对调制 {np.median(sd[m > 0.05 * m.max()] / m[m > 0.05 * m.max()]) * 100:.2f}%")
lo, hi = np.percentile(sd, 1), np.percentile(sd, 99.5)
img = np.clip((sd - lo) / max(hi - lo, 1e-9), 0, 1)
img8 = (img * 255).astype(np.uint8)
h, w = img8.shape
wx.Image(w, h, np.repeat(img8[:, :, None], 3, axis=2).tobytes()).SaveFile(out, wx.BITMAP_TYPE_PNG)
print("  saved", out)
