# -*- coding: utf-8 -*-
"""单掩膜（单次曝光）可行性数值实验。

用实测的 32 个散斑 PSF：
  1) 算每个核的 OTF 最小值 / 动态范围 —— 决定单次反卷积好不好做
  2) 用最好的那个核做单次仿真重建（合成 phantom + 噪声），报 PSNR

    python single_shot_sim.py --run runs\psf_b --iters 150
"""
from __future__ import annotations

import argparse
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from psf_recon import crop_kernels, psnr, reconstruct  # noqa: E402


def otf_stats(k: np.ndarray) -> tuple[float, float]:
    K = np.abs(np.fft.fft2(k))
    K = K / max(K.max(), 1e-12)
    return float(K.min()), float(K.mean())


def make_phantom(h: int, w: int) -> np.ndarray:
    """分辨率靶风格的 phantom：若干方孔 + 一条斜边。"""
    img = np.zeros((h, w))
    cy, cx = h // 2, w // 2
    # 中心 5x5 方孔阵列
    for i in range(-2, 3):
        for j in range(-2, 3):
            y0 = cy + i * 60 - 12
            x0 = cx + j * 80 - 14
            img[y0:y0 + 26, x0:x0 + 30] = 1.0
    # 一条竖直细缝 + 一条横缝
    img[cy - 100:cy + 100, cx - 160:cx - 150] = 0.8
    img[cy + 140:cy + 150, cx - 300:cx + 300] = 0.8
    return img


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default=r"runs\psf_b")
    ap.add_argument("--ksize", type=int, default=121)
    ap.add_argument("--iters", type=int, default=150)
    ap.add_argument("--lam", type=float, default=0.01)
    ap.add_argument("--noise", type=float, default=0.01, help="噪声标准差（相对峰值）")
    args = ap.parse_args(argv)

    psfs = np.load(os.path.join(args.run, "stack.npy")).astype(np.float64)
    psfs = np.maximum(psfs, 0)
    psfs /= np.maximum(psfs.sum(axis=(1, 2), keepdims=True), 1e-12)
    ks = crop_kernels(psfs, args.ksize)

    mins, means = [], []
    for k in ks:
        a, b = otf_stats(k)
        mins.append(a)
        means.append(b)
    order = np.argsort(mins)[::-1]
    print("OTF 最小值（越小越接近病态；1.0 = 完美 delta）")
    for i in order[:5]:
        print(f"  核 #{i:2d}  min {mins[i]:.4f}  mean {means[i]:.4f}")
    print(f"  最差 核 #{order[-1]:2d}  min {mins[order[-1]]:.4f}")

    # 单次仿真：用一个核
    for pick in [order[0], order[-1]]:
        h, w = 272, 482
        x = make_phantom(h, w)
        k = ks[pick]
        y = np.fft.irfft2(np.fft.rfft2(x) * _circ_k(k, (h, w)), (h, w))
        rng = np.random.default_rng(0)
        y = y + args.noise * y.max() * rng.standard_normal(y.shape)
        y = np.maximum(y, 0)
        rec, _ = reconstruct(ks[pick][None], y[None], lam=args.lam,
                             iters=args.iters, verbose=False)
        print(f"核 #{pick:2d}: 单次重建 PSNR {psnr(x, rec):5.2f} dB "
              f"(直接看被测图 {psnr(x, y):5.2f} dB)")
    return 0


def _circ_k(k: np.ndarray, shape: tuple[int, int]) -> np.ndarray:
    h, w = shape
    kh, kw = k.shape
    pad = np.zeros(shape)
    iy = (np.arange(kh) - kh // 2) % h
    ix = (np.arange(kw) - kw // 2) % w
    pad[np.ix_(iy, ix)] = k
    return np.fft.rfft2(pad)


if __name__ == "__main__":
    raise SystemExit(main())
