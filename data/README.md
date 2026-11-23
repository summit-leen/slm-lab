# 实验数据 — 2026-11-17 掩模成像

本目录是**可用（有效）**的实测数据，来自 2026-11-17 的 SLM 掩模成像实验。
失败/探索性采集（手机屏物体、相机 ROI 未复位、SLM 电源未开那几次）没有入库。

## 目录

```
data/2026-11-17/
├── raw/                    原始采集，每个 run 一个目录
│   ├── b_psf/              PSF：单张二元 0/π 随机掩模（100 µm 孔作点源）
│   ├── b_psf_flat/         同几何平场
│   ├── b_psf_d/            差值 PSF = b_psf − b_psf_flat（= result/psf_d.npy 的来源）
│   ├── e_bin/              物体：32 张随机二元掩模下的箭头
│   └── e_flat/             同几何平场
└── result/                 结果包（自带 README：文件说明、实验条件、关键数字、失败原因）
```

每个 run 里：

| 文件 | 含义 |
| --- | --- |
| `stack.npy` | float32 `(N, 544, 964)`，N 张掩模各自的多帧平均图（bin4，8 µm/px） |
| `meta.json` | SLM/相机/光几何参数、每张掩模的统计、用时 |
| `masks/` | 该 run 实际显示在 SLM 上的掩模（灰度数组，可由 seed 完全复现） |
| `psf/` | 逐掩模单帧（仅 b_psf 保留；e_bin 的 32 帧与 `stack.npy` 内容重复，已删） |

体积：`raw/` 83 MB，`result/` 71 MB，合计约 154 MB。

## 为什么这几条算“有效”

按工作日志 §3/§5 的判据（`code/psf_check.py` 可复算）：

- 无饱和像素（p99.9 < 55% 满量程，采集时 `--auto` 自动二分曝光）
- PSF 边缘/中心 = 0.313 → 光斑没有顶到靶面边缘
- 32 张掩模去共模后两两相关均值 −0.032、最大 0.045 → 掩模互相独立
- 90% 能量落在 28/32 个奇异值上（99% 需 31 个）→ 掩模多样性合格
- 箭头在靶面约 5.6×3.6 mm ≈ 3 个分辨元（λd/p = 1.72 mm，d = 50 mm）

## 已知的局限（不是数据坏了，是几何选小了）

- `result/arrow_recon_tv.npy` 的 TV+FISTA 重建**未收敛**：单张 PSF 用 541×541 大核，
  频域核动态范围跨几个量级，FISTA 步长被最小奇异值钉死，300 次迭代 data cost 只降 0.3%。
  结果仅留档，不要当成成功重建引用。
- 判决建议见 `result/README.md`「下次改进」：把 d 从 50 mm 缩到 15 mm，或改用菲涅尔
  透镜直接成像（`code/slm_lens.py`，f=150、d=s=300、离轴 tilt 0.10）。

## 复现 / 复算

```bash
# 重新采一组（会写进 runs/，与 data/ 无关）
python code/psf_capture.py --out runs/psf01 --auto --n 32 --frames 16 --bin 4 --seed 0 \
    --z-mm 40 --d-mm 40 --pinhole-um 15
# 判据
python code/psf_check.py runs/psf01 --cmsub
# 用本目录的差值数据直接重建
python code/psf_recon.py --run data/2026-11-17/raw/b_psf_d --obj data/2026-11-17/result/measure_32masks_minus_flat.npy --ksize 541 --noclip
```

## 说明

- 未收录：`b_obj*`、`obj_c/d/e`（相机 ROI 卡在 400×300、或物体太靠近点源导致的失败采集）、
  `g_bin`/`f_bin`（11-18 后续采集，标注与结论未整理）。需要时另开 `data/2026-11-18/`。
- `runs/`、`captures/` 是本地实时工作目录，已写进 `.gitignore`，不入库。
- 实验室内部数据，仓库为私有；对外发布前请先脱敏（`result/setup_photo.jpg` 含实验台场景）。
