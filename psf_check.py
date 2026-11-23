# -*- coding: utf-8 -*-
"""PSF 集质量诊断：采完先跑这个，判断这套掩模能不能做重建。

看四件事
--------
1. 饱和 / 边缘裁切：PSF 有没有被靶面切掉、有没有过曝；
2. 质心漂移：所有掩模的 PSF 质心应当一致（不一致说明有机械漂移或光源抖动）；
3. 两两相关性：掩模之间的 PSF 越不相关，重建矩阵越好；
4. 有效秩：SVD 之后多少奇异值就占到 90% 能量——这个数目才是你真正拿到的"独立测量数"。

用法
----
    python psf_check.py runs/psf01
    python psf_check.py runs/psf01 --crop 400
"""
from __future__ import annotations

import argparse
import json
import os

import numpy as np


def load_run(path: str) -> tuple[np.ndarray, dict]:
    stack = np.load(os.path.join(path, "stack.npy")).astype(np.float64)
    meta = {}
    meta_path = os.path.join(path, "meta.json")
    if os.path.exists(meta_path):
        with open(meta_path, encoding="utf-8") as f:
            meta = json.load(f)
    return stack, meta


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="PSF 集诊断")
    ap.add_argument("run", help="采集目录")
    ap.add_argument("--crop", type=int, default=0, help="只分析中心 crop x crop 区域")
    ap.add_argument("--cmsub", action="store_true",
                    help="先去掉共模（未调制背景）再算相关与有效秩")
    args = ap.parse_args(argv)

    stack, meta = load_run(args.run)
    n, h, w = stack.shape
    print(f"{args.run}: {n} 张 PSF, {w}x{h}")
    if meta:
        cam = meta.get("camera", {})
        optics = meta.get("optics", {})
        print(f"  相机 {cam.get('model')} bin={cam.get('binning', 1)} "
              f"曝光 {cam.get('exposure_us')} us")
        print(f"  几何 s={optics.get('z_mm')} mm, d={optics.get('d_mm')} mm, "
              f"针孔 {optics.get('pinhole_um')} um")

    if args.crop:
        c = min(args.crop, h, w)
        y0 = (h - c) // 2
        x0 = (w - c) // 2
        stack = stack[:, y0:y0 + c, x0:x0 + c]
        h, w = c, c

    # ---- 1. 饱和与边缘
    full = 4095.0 if stack.max() > 300 else 255.0
    sat = (stack >= full * 0.995).mean(axis=(1, 2)) * 100
    print(f"\n[饱和] 各图饱和比例 %: min {sat.min():.2f}, max {sat.max():.2f}")
    if sat.max() > 1:
        print("  [!] 有过曝，先降曝光或加衰减再采")

    edge = np.concatenate([stack[:, 0, :], stack[:, -1, :],
                           stack[:, :, 0], stack[:, :, -1]], axis=1).mean(axis=1)
    body = stack.mean(axis=(1, 2))
    spill = edge / np.maximum(body, 1e-9)
    print(f"[边缘] 边框平均/整体平均 = {spill.mean():.3f} (最大 {spill.max():.3f})")
    if spill.max() > 0.9:
        print("  [!] PSF 已经顶到靶面边缘，s 太大或掩模张角超出，会被裁切")

    # ---- 2. 质心
    yy, xx = np.mgrid[0:h, 0:w]
    tot = stack.sum(axis=(1, 2))
    ok = tot > 0
    cy = (stack * yy).sum(axis=(1, 2))[ok] / tot[ok]
    cx = (stack * xx).sum(axis=(1, 2))[ok] / tot[ok]
    print(f"[质心] x: {cx.mean():8.2f} ± {cx.std():.2f}   "
          f"y: {cy.mean():8.2f} ± {cy.std():.2f}  px")
    if max(cx.std(), cy.std()) > 2:
        print("  [!] 质心漂移超过 2 px，机械或光源不稳")

    # ---- 3. 相关性
    flat = stack.reshape(n, -1).astype(np.float64)
    if getattr(args, "cmsub", False):
        flat = flat - flat.mean(axis=0, keepdims=True)
        print("[去共模] 先减去所有掩模的平均图（未调制背景），再算相关与秩")
    flat = flat - flat.mean(axis=1, keepdims=True)
    norm = np.linalg.norm(flat, axis=1, keepdims=True)
    norm[norm == 0] = 1
    corr = (flat / norm) @ (flat / norm).T
    off = corr[~np.eye(n, dtype=bool)]
    print(f"[相关] 两两相关系数: 均值 {off.mean():.3f}, 最大 {off.max():.3f}")
    if off.max() > 0.95:
        print("  [!] 有掩模几乎相同，重建矩阵接近共线（无偏振片时很常见）")

    # ---- 4. 有效秩
    u, s, vt = np.linalg.svd(flat, full_matrices=False)
    energy = np.cumsum(s ** 2) / np.sum(s ** 2)
    rank90 = int(np.searchsorted(energy, 0.90) + 1)
    rank99 = int(np.searchsorted(energy, 0.99) + 1)
    print(f"[有效秩] 90% 能量需要 {rank90} 个奇异值 (共 {n})，99% 需要 {rank99} 个")
    print(f"  归一化奇异值: {np.array2string(s / s[0], precision=3, max_line_width=100)}")
    if rank90 < n * 0.3:
        print("  [!] 独立测量数远小于掩模数，这套 PSF 做重建会很病态")

    print("\n结论:", end=" ")
    if sat.max() > 1 and spill.max() > 0.9:
        print("先解决曝光和裁切，数据暂时不可用")
    elif rank90 < n * 0.3 or off.max() > 0.95:
        print("能重建但条件很差，建议加偏振片或换掩模族")
    else:
        print("可以进入重建")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
