# -*- coding: utf-8 -*-
"""把 SLM 上实际显示的图案（二元 0/π 掩模、菲涅尔透镜）补进结果文件夹。

用法: python -u add_slm_images.py
"""
import io
import os
import shutil

import numpy as np
from PIL import Image

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "result_20261117")
MASKS = os.path.join(ROOT, "runs", "e_bin", "masks")


def save_mask(npy, png):
    a = np.load(npy)
    if a.ndim == 3:
        a = a[..., 0]
    Image.fromarray(np.clip(a, 0, 255).astype(np.uint8)).save(png)
    return a


def main():
    os.makedirs(OUT, exist_ok=True)

    # 1) 单张掩模（拍第一帧时 SLM 上显示的就是这一张）
    if os.path.isdir(MASKS):
        names = sorted(f for f in os.listdir(MASKS) if f.endswith(".npy"))
        print("  找到 %d 张掩模" % len(names))
        a0 = save_mask(os.path.join(MASKS, names[0]),
                       os.path.join(OUT, "slm_mask_000.png"))
        shutil.copy2(os.path.join(MASKS, names[0]),
                     os.path.join(OUT, "slm_mask_000.npy"))
        print("  掩模 0 -> slm_mask_000.png / .npy  (shape %s, 取值 %s)"
              % (a0.shape, np.unique(a0)[:5]))

        # 前 4 张拼成一张对照图
        tiles = []
        for f in names[:4]:
            a = np.load(os.path.join(MASKS, f))
            if a.ndim == 3:
                a = a[..., 0]
            tiles.append(np.clip(a, 0, 255).astype(np.uint8))
        h, w = tiles[0].shape
        montage = np.zeros((2 * h, 2 * w), dtype=np.uint8)
        for i, t in enumerate(tiles):
            montage[(i // 2) * h:(i // 2 + 1) * h, (i % 2) * w:(i % 2 + 1) * w] = t
        Image.fromarray(montage).save(os.path.join(OUT, "slm_masks_0to3_montage.png"))
        print("  前 4 张 -> slm_masks_0to3_montage.png")
    else:
        print("  没有找到掩模目录:", MASKS)

    # 2) SLM 上显示过的菲涅尔透镜（截屏 / 图案文件）
    for src, dst in [
        (os.path.join(ROOT, "lens_on_slm.jpg"), "slm_lens_screenshot.jpg"),
        (os.path.join(ROOT, "lens150.png"), "slm_lens_pattern.png"),
        (os.path.join(ROOT, "lens.png"), "slm_lens_pattern.png"),
    ]:
        if os.path.exists(src) and not os.path.exists(os.path.join(OUT, dst)):
            shutil.copy2(src, os.path.join(OUT, dst))
            print("  ", src, "->", dst)

    extra = u"""
## SLM 上显示的图案

| 文件 | 内容 |
| --- | --- |
| `slm_mask_000.png` / `.npy` | 采第一帧时 SLM 上显示的二元 0/π 随机相位掩模，1024×768，灰度只有 0 和 198（198 = π 相位，实测 1.002π），填充率 50% |
| `slm_masks_0to3_montage.png` | 前 4 张掩模拼图，用来直观看出 32 张之间是互不相关的 |
| `slm_lens_screenshot.jpg` | 菲涅尔透镜图案（f=150 mm、离轴 tilt 0.10）显示在 SLM 上的截屏 |

掩模由 `psf_capture.py --mask binary --seed 0` 生成（`rng.random((768,1024)) < 0.5`
→ 198 / 0），同一 seed 可完全复现。采集脚本把每张掩模都存进了
`runs/<run>/masks/mask_XXX.npy`，32 张原始图案都在那里。
"""
    with io.open(os.path.join(OUT, "README.md"), "a", encoding="utf-8") as f:
        f.write(extra)
    print("  README.md 已追加 SLM 图案说明")

    print("\n文件夹内容:")
    for name in sorted(os.listdir(OUT)):
        print("  %-40s %8.2f MB" % (name, os.path.getsize(os.path.join(OUT, name)) / 1e6))


if __name__ == "__main__":
    main()
