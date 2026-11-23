"""匹配滤波（互相关）快速重建：y = h ⊛ x  ->  x_est = h ⋆ y

不迭代、不需要正则参数，几秒出结果，用来判定数据里到底有没有物体信息。

用法:
    python -u xcorr_recon.py --psf runs\\b_psf_d --obj runs\\b_obj_d\\stack.npy --out runs\\b_obj_d\\xcorr.npy
"""
import argparse
import json
import os

import numpy as np


def load_psf(run):
    stack = np.load(os.path.join(run, "stack.npy"))
    if stack.ndim == 2:
        stack = stack[None]
    return stack.astype(np.float64)


def render(path, out_png, pct=(0.5, 99.5)):
    from PIL import Image

    img = np.load(path).astype(np.float64)
    lo, hi = np.percentile(img, pct)
    img = np.clip((img - lo) / max(hi - lo, 1e-12), 0, 1)
    Image.fromarray((img * 255).astype(np.uint8)).save(out_png)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--psf", required=True, help="PSF run 目录（含 stack.npy）")
    ap.add_argument("--obj", required=True, help="测量数据 npy: (M,H,W) 或 (H,W)")
    ap.add_argument("--out", default=None, help="输出重建 npy")
    ap.add_argument("--png", default=None, help="输出 PNG")
    args = ap.parse_args()

    hs = load_psf(args.psf)
    y = np.load(args.obj).astype(np.float64)
    if y.ndim == 2:
        y = y[None]
    if hs.shape[1:] != y.shape[1:]:
        raise SystemExit("PSF 与测量尺寸不一致: %s vs %s" % (hs.shape, y.shape))

    acc = np.zeros(y.shape[1:], dtype=np.float64)
    for m in range(y.shape[0]):
        h = hs[m % hs.shape[0]]
        h = h - h.mean()
        ym = y[m] - y[m].mean()
        # 循环边界的互相关：x = ifft(conj(H) * Y)
        acc += np.fft.irfft2(np.conj(np.fft.rfft2(h)) * np.fft.rfft2(ym), s=ym.shape)

    acc /= y.shape[0]
    out = args.out or os.path.join(os.path.dirname(args.obj) or ".", "xcorr.npy")
    np.save(out, acc.astype(np.float32))
    print("xcorr 动态范围: min %.3g max %.3g std %.3g" % (acc.min(), acc.max(), acc.std()))

    # 找峰：物体在视场里的位置
    py, px = np.unravel_index(np.argmax(acc), acc.shape)
    print("相关峰位置: (x=%d, y=%d)，峰/标准差 = %.1f" % (px, py, acc.max() / max(acc.std(), 1e-12)))

    # 峰周围 3σ 内的能量占比（判断是不是单点）
    thr = acc.mean() + 5 * acc.std()
    print("超过 mean+5σ 的像素占比: %.4f%%" % (100.0 * (acc > thr).mean()))

    png = args.png or out.replace(".npy", ".png")
    render(out, png)
    print("已写出", out, "和", png)


if __name__ == "__main__":
    main()
