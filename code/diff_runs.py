# -*- coding: utf-8 -*-
"""把两次采集相减，得到"被调制的那部分光"的数据集。

为什么需要
----------
面板没有检偏器，只有约 8% 的光被相位调制，其余 92% 直穿。直穿光在靶面上
形成一层与掩模无关的底子（背景 / 零级），会把单掩膜重建完全带偏。
用"同一光路的两次采集"相减可以把它精确消掉：

    y = y_A - y_B,   h = h_A - h_B

只要两次之间只有 SLM 图案不同、其它一切不动。

典型用法
--------
    # 1) 拍"有掩模"的 PSF 与物体
    python psf_capture.py --mask binary --n 1 --seed 0 --out runs/b_psf
    python psf_capture.py --mask binary --n 1 --seed 0 --out runs/b_obj
    # 2) 拍"平场"（同一次会话、别动物体）
    python psf_capture.py --mask flat   --n 1 --out runs/b_psf_flat
    python psf_capture.py --mask flat   --n 1 --out runs/b_obj_flat
    # 3) 相减（PSF 与物体各一次）
    python diff_runs.py runs/b_psf runs/b_psf_flat --out runs/b_psf_d
    python diff_runs.py runs/b_obj runs/b_obj_flat --out runs/b_obj_d
    # 4) 重建
    python psf_recon.py --run runs/b_psf_d --obj runs/b_obj_d/stack.npy
"""
from __future__ import annotations

import argparse
import glob
import json
import os

import numpy as np


def _load_psfs(run: str) -> list[np.ndarray]:
    files = sorted(glob.glob(os.path.join(run, "psf", "psf_*.npy")))
    if not files:
        raise SystemExit(f"{run} 里没有 psf/psf_*.npy")
    return [np.load(f).astype(np.float32) for f in files]


def _load_stack(run: str) -> np.ndarray:
    p = os.path.join(run, "stack.npy")
    if not os.path.exists(p):
        raise SystemExit(f"{run} 里没有 stack.npy")
    return np.load(p).astype(np.float32)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="两次采集相减：A - B")
    ap.add_argument("a", help="run 目录（有掩模）")
    ap.add_argument("b", help="run 目录（平场）")
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)

    pa, pb = _load_psfs(args.a), _load_psfs(args.b)
    if len(pa) != len(pb):
        raise SystemExit(f"PSF 数量不一致: {len(pa)} vs {len(pb)}")
    sa, sb = _load_stack(args.a), _load_stack(args.b)
    if sa.shape != sb.shape:
        raise SystemExit(f"stack 形状不一致: {sa.shape} vs {sb.shape}")

    os.makedirs(os.path.join(args.out, "psf"), exist_ok=True)
    for i, (x, y) in enumerate(zip(pa, pb)):
        np.save(os.path.join(args.out, "psf", f"psf_{i:03d}.npy"), (x - y).astype(np.float32))

    d = sa - sb
    np.save(os.path.join(args.out, "stack.npy"), d.astype(np.float32))

    meta_p = os.path.join(args.a, "meta.json")
    meta = {}
    if os.path.exists(meta_p):
        with open(meta_p, "r", encoding="utf-8") as f:
            meta = json.load(f)
    meta["diff_of"] = [os.path.abspath(args.a), os.path.abspath(args.b)]
    meta["diff_stats"] = {
        "mean": float(d.mean()), "std": float(d.std()),
        "min": float(d.min()), "max": float(d.max()),
        "n_masks": int(d.shape[0]),
    }
    with open(os.path.join(args.out, "meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    print(f"{args.a} - {args.b}")
    print(f"  PSF  {len(pa)} 张, 形状 {pa[0].shape}")
    print(f"  差图 mean={d.mean():.2f} std={d.std():.2f} "
          f"min={d.min():.1f} max={d.max():.1f}")
    print(f"  已写入 {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
