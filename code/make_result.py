# -*- coding: utf-8 -*-
"""把这一轮的 PSF 与重建图像收集到一个文件夹里。

用法: python -u make_result.py
"""
import io
import os
import shutil

import numpy as np
from PIL import Image

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "result_20261117")


def render(src_npy, dst_png, pct=(0.5, 99.5)):
    a = np.load(src_npy).astype(np.float64)
    if a.ndim == 3:
        a = a.mean(axis=0)
    lo, hi = np.percentile(a, pct)
    a = np.clip((a - lo) / max(hi - lo, 1e-12), 0, 1)
    Image.fromarray((a * 255).astype(np.uint8)).save(dst_png)
    return dst_png


def copy(src, dst):
    if not os.path.exists(src):
        print("  跳过（不存在）:", src)
        return False
    shutil.copy2(src, dst)
    return True


def main():
    os.makedirs(OUT, exist_ok=True)

    # 1) PSF ---------------------------------------------------------
    src_psf = os.path.join(ROOT, "runs", "b_psf_d", "stack.npy")
    if copy(src_psf, os.path.join(OUT, "psf_d.npy")):
        render(os.path.join(OUT, "psf_d.npy"), os.path.join(OUT, "psf_d.png"))
        print("  PSF -> psf_d.npy / psf_d.png")

    # 2) 箭头图像（32 帧平均 + 高通）----------------------------------
    for src, dst in [
        (os.path.join(ROOT, "e_bin_mean.png"), "arrow_image.png"),
        (os.path.join(ROOT, "e_emph_highpass.png"), "arrow_highpass.png"),
    ]:
        if copy(src, os.path.join(OUT, dst)):
            print("  图像 ->", dst)

    # 3) TV 重建结果 -------------------------------------------------
    src_rec = os.path.join(ROOT, "runs", "e_recon2.npy")
    if copy(src_rec, os.path.join(OUT, "arrow_recon_tv.npy")):
        render(os.path.join(OUT, "arrow_recon_tv.npy"), os.path.join(OUT, "arrow_recon_tv.png"))
        print("  TV 重建 -> arrow_recon_tv.npy / .png")

    # 4) 原始 32 帧测量（可选，体积大）--------------------------------
    src_obj = os.path.join(ROOT, "runs", "e_obj_d.npy")
    if os.path.exists(src_obj):
        copy(src_obj, os.path.join(OUT, "measure_32masks_minus_flat.npy"))
        print("  测量 stack -> measure_32masks_minus_flat.npy")

    readme = u"""# SLM 掩模成像实验记录 2026-11-17

## 文件说明

| 文件 | 内容 |
| --- | --- |
| `psf_d.npy` / `psf_d.png` | 系统 PSF：100 µm 孔作点源、二元 0/π 随机相位掩模、减去平场后的差值图，544×964（bin4，8 µm/px） |
| `measure_32masks_minus_flat.npy` | 物体测量：箭头（黑卡抠孔）在光路中，32 张不同随机掩模的平均帧减去平场 |
| `arrow_image.png` | 32 帧平均得到的箭头图像（用户确认为箭头轮廓） |
| `arrow_highpass.png` | 上图的髙通增强，轮廓更清楚 |
| `arrow_recon_tv.npy` / `.png` | TV + FISTA 去卷积重建结果（未收敛，仅留档） |

## 实验条件

- 光源：大恒 GCI-060401 红光 LED，620 nm，120°
- 点源：100 µm 小孔（孔板背面贴黑卡防漫反射）
- 调制器：大恒 GCI-770202 透射式 TN-LCD SLM，1024×768，18 µm 像素间距
  - 相位行程 Γ=400 nm，620 nm 下总量 1.29π
  - π 相位对应灰度 198（实测 1.002π），二元图案填充率 50%
  - 无检偏器，调制深度约 8~17%（随几何变化）
- 相机：Basler daA3840-45um，bin4，964×544，8 µm/px，曝光 2000 µs
- 几何：孔 → 50 mm → SLM → 40 mm → 相机

## 关键数字

- 分辨率 λd/p = 0.62 µm × 50 mm / 18 µm = **1.72 mm**（只由 d 决定，与 s 无关）
- 箭头在靶面上约 5.6×3.6 mm，即约 3 个分辨元 —— 已经接近这个几何的极限
- 32 张掩模去共模后两两相关 −0.03（最大 0.045），90% 能量需 28 个奇异值 → 掩模多样性合格
- 边缘平均/中心平均 = 0.313，PSF 没有顶到靶面边缘

## 重建失败的原因（留档）

单张 PSF 用 541×541 大核，频域核动态范围跨数个量级，FISTA 步长 1/L 被最小
奇异值钉死：300 次迭代 data cost 只从 8.447e6 降到 8.4466e6（0.3%），解没走出来。

## 下次改进

1. **把 d 从 50 mm 缩到 15 mm**：分辨率升到 0.52 mm（3.3 倍），箭头会有约 10 个分辨元
   - 放大率变成 s/d = 2.7，箭头需缩到 2.5 mm 左右（否则 13.5 mm > 7.7 mm 靶面）
2. 或用菲涅尔透镜直接成像（f=150，d=s=300，离轴 tilt 0.10），不重建、直接看实像
3. 加线偏振片可把调制深度从 8% 提到接近 100%

## 相关脚本（同目录上一级）

`D:\\课题组\\slm\\`：psf_capture.py（采集）、psf_recon.py（重建）、psf_check.py（判据）、
diff_flat.py / diff_runs.py（去平场、去共模）、view_stack.py / emphasize.py（可视化）、
slm_binary.py（二元掩模显示）、slm_lens.py（菲涅尔透镜）
"""
    with io.open(os.path.join(OUT, "README.md"), "w", encoding="utf-8") as f:
        f.write(readme)
    print("  README.md 已写出")

    print("\n文件夹内容:")
    for name in sorted(os.listdir(OUT)):
        p = os.path.join(OUT, name)
        print("  %-38s %8.2f MB" % (name, os.path.getsize(p) / 1e6))


if __name__ == "__main__":
    main()
