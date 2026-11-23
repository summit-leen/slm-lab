# -*- coding: utf-8 -*-
"""检查 PSF 集合在"去掉共模"前后的有效秩。"""
from __future__ import annotations

import sys

import numpy as np

run = sys.argv[1] if len(sys.argv) > 1 else r"runs\psf_a"
s = np.load(run + r"\stack.npy").astype(np.float64)
n = len(s)
print(f"{n} 张 PSF, 形状 {s.shape[1:]}, 均值 {s.mean():.1f}")

flat = s.reshape(n, -1)
raw = flat - flat.mean(1, keepdims=True)
u, sv, vt = np.linalg.svd(raw, full_matrices=False)
print("原图 (去各自均值):", np.round(sv / sv[0], 4))

m = flat.mean(0, keepdims=True)
res = flat - m
u2, sv2, vt2 = np.linalg.svd(res, full_matrices=False)
print("去共模后:", np.round(sv2 / sv2[0], 4))
e = np.cumsum(sv2 ** 2) / np.sum(sv2 ** 2)
print("累计能量:", np.round(e, 3))

# 残差之间的相关系数
r = res - res.mean(1, keepdims=True)
rn = r / np.linalg.norm(r, axis=1, keepdims=True)
c = rn @ rn.T
off = c[np.triu_indices(n, 1)]
print(f"去共模后两两相关: 均值 {off.mean():.3f}, 最大 {off.max():.3f}")

# 调制深度：一张图相对共模的差异
for i in range(min(n, 4)):
    d = res[i]
    print(f"  mask {i}: |residual|/mean = {np.abs(d).mean() / s[i].mean() * 100:.2f}%")
