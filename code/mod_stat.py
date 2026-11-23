# -*- coding: utf-8 -*-
"""报告一组 stack 的调制强度：逐像素跨掩模标准差 / 均值。"""
import sys
import numpy as np

for path in sys.argv[1:]:
    s = np.load(path).astype(np.float64)
    if s.ndim == 2:
        print(f"{path}: 单张 2D，跳过"); continue
    m = s.mean(axis=0)
    sd = s.std(axis=0)
    msk = m > (0.05 * m.max())
    mod = (sd[msk] / m[msk])
    print(f"{path}")
    print(f"  shape {s.shape}  mean {m.mean():.1f}  max {m.max():.0f}")
    print(f"  逐像素 std/mean: 中位 {np.median(mod) * 100:.2f}%  "
          f"90 分位 {np.percentile(mod, 90) * 100:.2f}%  "
          f"最大 {mod.max() * 100:.2f}%")
    print(f"  跨掩模最大差 / 全图均值: {np.abs(s.max(axis=0) - s.min(axis=0)).mean() / m.mean() * 100:.2f}%")
