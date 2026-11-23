# -*- coding: utf-8 -*-
"""在 SLM 上显示二元随机相位掩模（0 / π），用于单掩膜重建。

相位映射
--------
面板相位 = 2*pi * alpha * gray/255，alpha = Gamma/lambda = 400/620 = 0.645。
所以：
    灰 0   -> 相位 0
    灰 198 -> 相位 = 2*pi*0.645*198/255 = 3.14 rad = pi
二元 0/π 的 50/50 随机图案，其平均场为 0（+1 与 -1 相消），
所以没有强零级，光被均匀散到整个靶面（比随机灰度掩模更适合免重建/单次重建）。

用法
----
    python slm_binary.py --seed 0 --hold 600
    python slm_binary.py --seed 3 --block 2 --save bin3.npy
    python slm_binary.py --info            # 只打印参数，不显示
"""
from __future__ import annotations

import argparse
import math
import os

import numpy as np

DEFAULT_LAM_NM = 620.0
DEFAULT_GAMMA_NM = 400.0


def make_binary(width: int, height: int, seed: int, fill: float = 0.5,
                block: int = 1, pi_gray: int = 198) -> np.ndarray:
    rng = np.random.default_rng(seed)
    hh, ww = height, width
    if block > 1:
        hh, ww = height // block, width // block
    m = rng.random((hh, ww)) < fill
    img = np.where(m, pi_gray, 0).astype(np.uint8)
    if block > 1:
        img = np.repeat(np.repeat(img, block, axis=0), block, axis=1)
        img = img[:height, :width]
    return img


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="二元随机相位掩模 0/π")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--fill", type=float, default=0.5, help="π 像素占比 (默认 0.5)")
    ap.add_argument("--block", type=int, default=1, help="像素块大小 (1=逐像素)")
    ap.add_argument("--lam", type=float, default=DEFAULT_LAM_NM)
    ap.add_argument("--gamma", type=float, default=DEFAULT_GAMMA_NM)
    ap.add_argument("--pi-gray", type=int, default=None,
                    help="π 对应的灰度 (默认按 gamma/lam 自动算，620nm 时 = 198)")
    ap.add_argument("--monitor", type=int, default=1)
    ap.add_argument("--hold", type=float, default=600.0)
    ap.add_argument("--save", default=None)
    ap.add_argument("--info", action="store_true")
    args = ap.parse_args(argv)

    alpha = min(1.0, args.gamma / args.lam)
    pi_gray = args.pi_gray if args.pi_gray is not None else int(round(255.0 * 0.5 / alpha))
    phase_step = 2.0 * math.pi * alpha * pi_gray / 255.0

    print(f"alpha = Gamma/lambda = {args.gamma:g}/{args.lam:g} = {alpha:.3f} 周期 "
          f"({2*alpha:.2f}pi rad 总行程)")
    print(f"pi 相位 -> 灰度 {pi_gray} -> 实际相位 {phase_step:.3f} rad "
          f"({phase_step/math.pi:.3f}pi)")
    print(f"二元 0/{pi_gray}, fill={args.fill:g}, block={args.block}, seed={args.seed}")

    if args.info:
        return 0

    from slm_driver import SLM

    slm = SLM(monitor=args.monitor, verbose=False)
    w, h = slm.getSize()
    img = make_binary(w, h, args.seed, args.fill, args.block, pi_gray)
    frac = float((img > 0).mean())
    print(f"图案 {w}x{h}, pi 像素占 {frac*100:.1f}%, 灰度范围 {img.min()}..{img.max()}")
    if args.save:
        np.save(args.save, img)
        print("已保存", args.save)

    print(f"显示 {args.hold:g} s ...")
    slm.update(img)
    slm.run()
    print("结束")
    import sys
    sys.stdout.flush()
    os._exit(0)


if __name__ == "__main__":
    raise SystemExit(main())
