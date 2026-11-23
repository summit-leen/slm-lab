# -*- coding: utf-8 -*-
"""把 .npy 图像打成 ASCII 缩略图，看结构用（不装 matplotlib 也能看）。"""
import sys

import numpy as np

RAMP = " .:-=+*#%@"


def main(path: str, cols: int = 64) -> int:
    img = np.load(path).astype(np.float64)
    if img.ndim == 3:
        img = img[0]
    h, w = img.shape
    rows = max(1, int(round(cols * h / w / 2.0)))
    ys = np.linspace(0, h, rows + 1).astype(int)
    xs = np.linspace(0, w, cols + 1).astype(int)

    blocks = np.zeros((rows, cols))
    for i in range(rows):
        for j in range(cols):
            blocks[i, j] = img[ys[i]:ys[i + 1], xs[j]:xs[j + 1]].mean()

    lo, hi = float(img.min()), float(img.max())
    print(f"{path}: {w}x{h}  min={lo:.0f} max={hi:.0f} mean={img.mean():.1f} "
          f"p99.9={np.percentile(img, 99.9):.0f}")
    span = max(hi - lo, 1e-9)
    for i in range(rows):
        line = "".join(RAMP[min(len(RAMP) - 1, int((v - lo) / span * (len(RAMP) - 1) + 0.5))]
                       for v in blocks[i])
        print(line)

    # 峰值位置与半高宽（粗略）
    py, px = np.unravel_index(np.argmax(img), img.shape)
    print(f"argmax at ({px},{py}) = {img.max():.0f}")
    prof = img.mean(axis=0)
    half = (prof.max() + prof.min()) / 2
    above = np.where(prof >= half)[0]
    if above.size:
        print(f"horizontal FWHM ≈ {above[-1]-above[0]+1} px")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 64))
