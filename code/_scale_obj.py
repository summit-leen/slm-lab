# -*- coding: utf-8 -*-
"""把物体 stack 乘上曝光比，换算到与 PSF stack 同一辐照度标度。"""
import numpy as np

src = r"D:\课题组\slm\runs\obj_c\stack.npy"
dst = r"D:\课题组\slm\runs\obj_c\obj_scaled.npy"
RATIO = 590.0 / 4000.0  # PSF 用 590 us 采，物体用 4000 us

s = np.load(src).astype(np.float32) * RATIO
np.save(dst, s)
print("shape", s.shape, "mean", float(s.mean()), "->", dst)
