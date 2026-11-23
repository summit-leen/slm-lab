"""把 stack 的平均图做高通增强，突出物体轮廓（无 scipy 依赖，用 PIL 高斯模糊）。

用法:
    python -u emphasize.py runs/e_bin D:\\...\\out.png [--radius 15] [--frame -1]
"""
import argparse
import os

import numpy as np
from PIL import Image, ImageFilter


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("run")
    ap.add_argument("out")
    ap.add_argument("--radius", type=float, default=15.0)
    ap.add_argument("--frame", type=int, default=-1, help="-1 表示用 32 帧平均")
    ap.add_argument("--mode", default="unsharp", choices=["unsharp", "highpass", "both"])
    args = ap.parse_args()

    stack = np.load(os.path.join(args.run, "stack.npy")).astype(np.float64)
    img = stack.mean(axis=0) if args.frame < 0 else stack[args.frame]
    if stack.ndim == 2:
        img = stack

    lo, hi = np.percentile(img, (0.5, 99.5))
    base = np.clip((img - lo) / max(hi - lo, 1e-9), 0, 1)

    pil = Image.fromarray((base * 255).astype(np.uint8))
    blur = np.asarray(pil.filter(ImageFilter.GaussianBlur(args.radius)), dtype=np.float64) / 255.0

    hp = base - blur
    for name, arr in (("highpass", hp), ("unsharp", base + 1.5 * hp)):
        a = np.clip(arr, 0, 1)
        # 用 2%~98% 分位拉伸，让轮廓最清楚
        p2, p98 = np.percentile(a, (2, 98))
        a = np.clip((a - p2) / max(p98 - p2, 1e-9), 0, 1)
        out = args.out.replace(".png", "_%s.png" % name)
        Image.fromarray((a * 255).astype(np.uint8)).save(out)
        print("saved", out, "range %.3f..%.3f" % (a.min(), a.max()))


if __name__ == "__main__":
    main()
