"""把 n 帧的 stack 减去单帧平场（广播），输出差值 stack 的 npy。

用法:
    python -u diff_flat.py runs/e_bin runs/e_flat runs/e_obj_d.npy
"""
import os
import sys

import numpy as np

if len(sys.argv) != 4:
    raise SystemExit(__doc__)

src, flat, dst = sys.argv[1:4]


def load(p):
    path = p if p.endswith(".npy") else os.path.join(p, "stack.npy")
    a = np.load(path).astype(np.float64)
    return a if a.ndim == 3 else a[None]


a = load(src)
b = load(flat)
out = a - b[0][None, ...]
np.save(dst, out.astype(np.float32))
print("差值: %s (%d 帧) - %s (1 帧) -> %s" % (src, a.shape[0], flat, dst))
print("  mean=%.2f std=%.2f min=%.1f max=%.1f" % (out.mean(), out.std(), out.min(), out.max()))
