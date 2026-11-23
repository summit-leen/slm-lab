# -*- coding: utf-8 -*-
"""用测到的 PSF 集做图像重建（多掩模联合解卷积 + TV 正则）。

模型
----
每个掩模一次测量：  y_m = h_m ⊛ x + n_m
（h_m 是实测 PSF，x 是物面强度，⊛ 表示线性卷积）
联合求  min_x  Σ_m ½||h_m ⊛ x - y_m||² + λ·TV(x),  x >= 0

用法
----
    :: 用真实数据
    python psf_recon.py --run runs/psf01 --obj runs/psf01/obj.npy --out runs/psf01/recon.npy

    :: 先跑自检（合成数据，验证代码通不通，不代表真实系统性能）
    python psf_recon.py --selftest runs\selftest
"""
from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np


# ---------------------------------------------------------------- 基础算子
def conv_same(x: np.ndarray, k: np.ndarray) -> np.ndarray:
    """线性卷积，输出与 x 同尺寸（零填充，无环绕）。"""
    h, w = x.shape
    kh, kw = k.shape
    shape = (h + kh - 1, w + kw - 1)
    out = np.fft.irfft2(np.fft.rfft2(x, shape) * np.fft.rfft2(k, shape), shape)
    oy, ox = (kh - 1) // 2, (kw - 1) // 2
    return out[oy:oy + h, ox:ox + w]


def conv_adj(y: np.ndarray, k: np.ndarray) -> np.ndarray:
    """卷积算子的伴随 = 用翻转的核再卷一次。"""
    return conv_same(y, k[::-1, ::-1])


def _kernel_spectrum_circ(k: np.ndarray, shape: tuple[int, int]) -> np.ndarray:
    """把核中心对齐到 (0,0) 后补零到 shape，返回循环卷积用的 rfft2 谱。"""
    h, w = shape
    kh, kw = k.shape
    pad = np.zeros(shape, dtype=np.float64)
    iy = (np.arange(kh) - kh // 2) % h
    ix = (np.arange(kw) - kw // 2) % w
    pad[np.ix_(iy, ix)] = k
    return np.fft.rfft2(pad)


def _div(px: np.ndarray, py: np.ndarray) -> np.ndarray:
    out = np.zeros_like(px)
    out[:, 1:] += px[:, 1:] - px[:, :-1]
    out[:, 0] += px[:, 0]
    out[1:, :] += py[1:, :] - py[:-1, :]
    out[0, :] += py[0, :]
    return out


def prox_tv(b: np.ndarray, lam: float, iters: int = 40, tau: float = 0.125) -> np.ndarray:
    """Chambolle 投影法求 min_u ½||u-b||² + lam·TV(u)。"""
    if lam <= 0:
        return b.copy()
    px = np.zeros_like(b)
    py = np.zeros_like(b)
    for _ in range(iters):
        v = _div(px, py) - b / lam
        gx = np.zeros_like(b)
        gy = np.zeros_like(b)
        gx[:, :-1] = v[:, 1:] - v[:, :-1]
        gy[:-1, :] = v[1:, :] - v[:-1, :]
        n = np.sqrt(gx * gx + gy * gy)
        px = (px + tau * gx) / (1.0 + tau * n)
        py = (py + tau * gy) / (1.0 + tau * n)
    return b - lam * _div(px, py)


def psnr(a: np.ndarray, b: np.ndarray) -> float:
    mse = float(np.mean((a - b) ** 2))
    peak = float(max(a.max(), b.max(), 1e-12))
    return 10.0 * np.log10(peak ** 2 / max(mse, 1e-20))


# ---------------------------------------------------------------- 重建
def reconstruct(psfs: np.ndarray, ys: np.ndarray, lam: float = 0.02,
                iters: int = 300, tv_iters: int = 30, verbose: bool = True) -> np.ndarray:
    """FISTA + TV。卷积用循环边界：正/伴随严格成对，每次迭代只需 2 次 FFT。

    图像边缘会有 <= 核半径的环绕伪影，对重建结果内部无影响。
    """
    n, kh, kw = psfs.shape
    ys = ys.reshape(n, *ys.shape[-2:])
    h, w = ys.shape[1:]
    shape = (h, w)

    # 归一化：把 h 和 y 同时除以 c，解 x 不变，但数据项的绝对量级从 ~1e10
    # 降到 ~1e6，TV 权重 lam 才真正起作用（否则 lam=0.02 相对数据项等于 0，
    # 解会退化成稀疏亮点）。
    c = float(ys.std())
    if not np.isfinite(c) or c <= 0:
        c = 1.0
    if verbose:
        print(f"  归一化：h、y 同除 {c:.6g}（lam={lam} 相当于原尺度 {lam * c * c:.4g}）", flush=True)
    ys = ys / c
    psfs = psfs / c

    # grad(z) = Σ_m A_m^T (A_m z - y_m) = irfft2( S·Ẑ - T )
    #   S = Σ|K̂_m|²,  T = Σ conj(K̂_m)·Ŷ_m —— 全部预先合成
    nf = shape[1] // 2 + 1
    S = np.zeros((shape[0], nf), dtype=np.float64)
    T = np.zeros((shape[0], nf), dtype=np.complex128)
    Kfs = np.empty((n, shape[0], nf), dtype=np.complex64)
    for i, (k, y) in enumerate(zip(psfs, ys)):
        Kf = _kernel_spectrum_circ(k, shape)
        Kfs[i] = Kf.astype(np.complex64)
        S += np.abs(Kf) ** 2
        T += np.conj(Kf) * np.fft.rfft2(y)
    lip = max(float(S.max()), 1e-12)

    def grad(z: np.ndarray) -> np.ndarray:
        return np.fft.irfft2(S * np.fft.rfft2(z) - T, shape)

    def cost_of(x: np.ndarray) -> float:
        X = np.fft.rfft2(x)
        tot = 0.0
        for i, y in enumerate(ys):
            tot += float(np.sum((np.fft.irfft2(Kfs[i] * X, shape) - y) ** 2))
        return 0.5 * tot

    x = np.maximum(ys.mean(axis=0), 0).astype(np.float64)
    z = x.copy()
    t = 1.0
    history = []
    for it in range(iters):
        g = grad(z)
        xn = prox_tv(np.maximum(z - g / lip, 0.0), lam / lip, tv_iters)
        t_next = 0.5 * (1.0 + np.sqrt(1.0 + 4.0 * t * t))
        z = xn + (t - 1.0) / t_next * (xn - x)
        x = xn
        t = t_next
        if it % 50 == 0 or it == iters - 1:
            cost = cost_of(x)
            history.append(cost)
            if verbose:
                print(f"  iter {it:4d}  data cost {cost:12.4f}", flush=True)
    return x, history


def crop_kernels(psfs: np.ndarray, size: int) -> np.ndarray:
    n, h, w = psfs.shape
    size = min(size, h, w)
    out = np.zeros((n, size, size))
    for i in range(n):
        p = psfs[i]
        yy, xx = np.mgrid[0:h, 0:w]
        cy = float((p * yy).sum() / max(p.sum(), 1e-12))
        cx = float((p * xx).sum() / max(p.sum(), 1e-12))
        y0 = int(round(cy - size / 2))
        x0 = int(round(cx - size / 2))
        y0 = max(0, min(h - size, y0))
        x0 = max(0, min(w - size, x0))
        k = p[y0:y0 + size, x0:x0 + size].copy()
        s = k.sum()
        out[i] = k / s if s > 0 else k
    return out


# ---------------------------------------------------------------- 自检
def selftest(out_dir: str, size: int = 160, n_masks: int = 8, seed: int = 0) -> int:
    rng = np.random.default_rng(seed)
    os.makedirs(out_dir, exist_ok=True)

    # 1) 掩模 -> 远场强度，裁成 K x K 当"PSF"（只用于验证代码，不预测真实 PSF 形状）
    K = 41
    psfs = np.zeros((n_masks, K, K))
    for i in range(n_masks):
        phase = rng.uniform(0, 1.29 * np.pi, size=(256, 256))
        field = np.exp(1j * phase)
        inten = np.abs(np.fft.fftshift(np.fft.fft2(field))) ** 2
        c = inten.shape[0] // 2
        k = inten[c - K // 2:c + K // 2 + 1, c - K // 2:c + K // 2 + 1].copy()
        io = np.fft.ifftshift(np.fft.fft2(k))     # 让 PSF 峰值居中，卷积时相位正常
        k = np.abs(np.fft.fftshift(io))
        psfs[i] = k / k.sum()

    # 2) 物：几个圆盘 + 方条
    yy, xx = np.mgrid[0:size, 0:size]
    gt = np.zeros((size, size))
    gt[(yy - 40) ** 2 + (xx - 45) ** 2 < 18 ** 2] = 1.0
    gt[(yy - 105) ** 2 + (xx - 100) ** 2 < 24 ** 2] = 0.7
    gt[60:75, 20:140] = 0.9
    gt = gt + 0.02 * rng.standard_normal(gt.shape)
    gt = np.maximum(gt, 0)

    # 3) 测量
    ys = np.stack([conv_same(gt, psfs[i]) for i in range(n_masks)])
    ys = ys + 0.002 * rng.standard_normal(ys.shape)
    ys = np.maximum(ys, 0)

    np.save(os.path.join(out_dir, "stack.npy"), psfs)
    np.save(os.path.join(out_dir, "obj.npy"), ys)
    np.save(os.path.join(out_dir, "gt.npy"), gt)
    with open(os.path.join(out_dir, "meta.json"), "w", encoding="utf-8") as f:
        json.dump({"selftest": True, "n_masks": n_masks, "psf_size": K,
                   "note": "合成数据，仅验证代码"}, f, ensure_ascii=False, indent=2)

    baseline = psnr(gt, ys.mean(axis=0))
    print(f"直接平均基线 PSNR {baseline:.2f} dB")
    rec, _ = reconstruct(psfs, ys, lam=0.005, iters=200, verbose=True)
    print(f"重建 PSNR {psnr(gt, rec):.2f} dB  (提升 {psnr(gt, rec) - baseline:+.2f} dB)")
    np.save(os.path.join(out_dir, "recon.npy"), rec.astype(np.float32))
    return 0


# ---------------------------------------------------------------- 入口
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="多掩模 PSF 联合重建")
    ap.add_argument("--selftest", default=None, help="合成数据自检，参数是输出目录")
    ap.add_argument("--run", default=None, help="采集目录（含 stack.npy）")
    ap.add_argument("--obj", default=None, help="测量数据 npy: (M,H,W) 或 (H,W)")
    ap.add_argument("--gt", default=None, help="真值 npy（可选，用于算 PSNR）")
    ap.add_argument("--out", default=None, help="重建结果输出路径")
    ap.add_argument("--ksize", type=int, default=121, help="PSF 裁成多大的核")
    ap.add_argument("--lam", type=float, default=0.01, help="TV 权重")
    ap.add_argument("--iters", type=int, default=300)
    ap.add_argument("--cmsub", action="store_true",
                    help="去掉共模：PSF 与测量都减掉各自的均值。")
    ap.add_argument("--noclip", action="store_true",
                    help="测量是差值时用，不要把测量裁到 >=0。")
    args = ap.parse_args(argv)

    if args.selftest:
        return selftest(args.selftest)
    if not args.run or not args.obj:
        ap.error("要么 --selftest，要么同时给 --run 和 --obj")

    psfs = np.load(os.path.join(args.run, "stack.npy")).astype(np.float64)
    psfs = np.maximum(psfs, 0)
    psfs /= np.maximum(psfs.sum(axis=(1, 2), keepdims=True), 1e-12)
    ks = crop_kernels(psfs, args.ksize)

    ys = np.load(args.obj).astype(np.float64)
    if ys.ndim == 2:
        ys = ys[None]
    # 单张 PSF 可以复用到所有测量帧（点源响应不变的情形）
    if ks.shape[0] == 1 and ys.shape[0] > 1:
        ks = np.repeat(ks, ys.shape[0], axis=0)
        print(f"单张 PSF 复用到 {ys.shape[0]} 帧")
    if ys.shape[0] != ks.shape[0]:
        raise SystemExit(f"测量 {ys.shape[0]} 张，PSF {ks.shape[0]} 张，对不上")
    if not args.noclip:
        ys = np.maximum(ys, 0)

    print(f"{ks.shape[0]} 个掩模, 核 {ks.shape[1]}x{ks.shape[2]}, 视场 {ys.shape[1]}x{ys.shape[2]}")
    if args.cmsub:
        km = ks.mean(axis=0)
        ym = ys.mean(axis=0)
        ks = ks - km
        ys = ys - ym
        print(f"去共模后: 核能量 {np.abs(ks).sum(axis=(1, 2)).mean():.4f}, "
              f"测量均值 {ym.mean():.1f} 已减掉")
    rec, _ = reconstruct(ks, ys, lam=args.lam, iters=args.iters)

    if args.gt:
        gt = np.load(args.gt).astype(np.float64)
        print(f"PSNR {psnr(gt, rec):.2f} dB (直接平均基线 {psnr(gt, ys.mean(axis=0)):.2f} dB)")

    out = args.out or os.path.join(args.run, "recon.npy")
    np.save(out, rec.astype(np.float32))
    print(f"已保存 {out}")
    sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
