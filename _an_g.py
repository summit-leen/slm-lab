# -*- coding: utf-8 -*-
"""分析新采的 g_bin / g_flat：调制深度、与昨天 PSF 的相关、导出 PNG。"""
import os
import numpy as np
from PIL import Image

R = os.path.dirname(os.path.abspath(__file__))


def save_png(a, path, lo=0.5, hi=99.5):
    lo_v, hi_v = np.percentile(a, [lo, hi])
    b = np.clip((a - lo_v) / max(hi_v - lo_v, 1e-9), 0, 1) * 255
    Image.fromarray(b.astype(np.uint8)).save(path)


stack = np.load(os.path.join(R, "runs", "g_bin", "stack.npy")).astype(np.float64)
flat = np.load(os.path.join(R, "runs", "g_flat", "stack.npy")).astype(np.float64)[0]
print("stack", stack.shape, "flat", flat.shape)
print("stack mean %.1f  max %.1f  sat>=4095 %.2f%%" % (
    stack.mean(), stack.max(), 100.0 * (stack >= 4095).mean()))
print("flat  mean %.1f  max %.1f" % (flat.mean(), flat.max()))

diff = stack - flat[None, :, :]
print("差异: mean %.2f  std %.2f  min %.1f  max %.1f" % (
    diff.mean(), diff.std(), diff.min(), diff.max()))
mod = stack.std(axis=0) / np.maximum(stack.mean(axis=0), 1e-6)
print("调制深度: 中位 %.3f%%  最大 %.3f%%" % (100 * np.median(mod), 100 * mod.max()))

psf = np.load(os.path.join(R, "runs", "b_psf_d", "psf", "psf_000.npy")).astype(np.float64)
obj = diff.mean(axis=0)
if psf.shape != obj.shape:
    h = min(psf.shape[0], obj.shape[0])
    w = min(psf.shape[1], obj.shape[1])
    psf = psf[:h, :w]
    obj = obj[:h, :w]
A = psf - psf.mean()
B = obj - obj.mean()
r = float((A * B).sum() / np.sqrt((A * A).sum() * (B * B).sum()))
print("与昨天 PSF 的相关系数 r = %.4f" % r)

save_png(stack.mean(axis=0), os.path.join(R, "g_mean.png"))
save_png(obj, os.path.join(R, "g_diff_mean.png"))
save_png(psf, os.path.join(R, "g_psf_cmp.png"))
print("saved g_mean.png / g_diff_mean.png / g_psf_cmp.png")
