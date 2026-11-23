# SLM 控制环境（Windows）

给液晶 SLM（当作第二块显示器使用）输出相位/灰度图案的最小可用环境，
外加一套把它当"编码孔径成像系统"用的采集—判据—重建工具链。

> **2026-11-23 的随机透镜阵列 / 散斑实验**（七种图案、14 组相机帧、轴向 PSF 扫描）
> 单独放在 <https://github.com/summit-leen/random-lens-array-2026-11-23>，
> 那边用的是本仓库的脚本，数据与过程记录在它的 `docs/experiment-log.md`。

## 0. 仓库结构

```
slm-lab/
├── code/        全部脚本（.py + 4 个 PowerShell 辅助脚本），互相同目录 import
├── data/        实测数据：2026-11-17 掩模成像（有效采集 + 结果包），见 data/README.md
├── docs/        工作日志、多掩膜光路图绘制说明、辅助文本
├── figures/     过程图与对比图（PNG/JPG，供文档和 PPT 引用）
├── patterns/    SLM 相位图案产物（npy/png/csv，可由 seed 复现）
├── logs/        历史采集日志（.log）
├── runs/        本地实时采集目录（已 .gitignore，不入库）
└── captures/    相机原始抓图（已 .gitignore）
```

脚本都在仓库根目录下用 `python code/xxx.py` 调用；脚本内部的相对路径
（`runs/…`、`patterns/…`）按当前工作目录解析。

## 1. 硬件与显示配置

| 项目 | 值 |
| --- | --- |
| 主屏 | `\\.\DISPLAY1` 2560x1600，150% 缩放，内部屏（Lenovo DisplayHDR CSO1612） |
| SLM 通道 | `\\.\DISPLAY2` 1024x768，100% 缩放，位于 (2560, 0)，HDMI 输出（RGT1352） |
| 显示模式 | **扩展**（不能是"复制"；复制模式下 SLM 拿到的是 2560x1600 缩放插值后的画面） |

`python code/slm_show.py --info` 可随时确认拓扑。若重启后变回复制模式，需在
设置 → 系统 → 屏幕 里重新选"扩展这些显示器"，并把第二屏设成 100% 缩放。

## 2. Python 环境

| 项目 | 值 |
| --- | --- |
| 解释器 | `C:\Users\19414\AppData\Local\Microsoft\WindowsApps\python.exe`（Microsoft Store 版 3.12.10 x64） |
| 用户级包目录 | `C:\Users\19414\AppData\Local\Packages\PythonSoftwareFoundation.Python.3.12_qbz5n2kfra8p0\LocalCache\local-packages\Python312\site-packages` |
| numpy | 1.26.4 |
| wxPython | 4.3.2（Phoenix, wxWidgets 3.3.4） |
| slmpy | 0.3.3，源码取自 github.com/wavefrontshaping/slmPy，手工放进 site-packages\slmpy（PyPI 的 sdist 的 setup.py 依赖 pkgconfig，装不上） |

安装脚本备忘（需要完全权限，沙箱下 pip 会因写系统临时目录被拒）：

```cmd
python -m pip install --user --no-cache-dir numpy wxpython
```

## 3. 用法

```cmd
python code/slm_show.py --info                    :: 看显示器拓扑
python code/slm_show.py frame --hold 20           :: 对齐框（边框 + 十字 + 角标 + 128px 点阵）
python code/slm_show.py grating --period 16 --hold 30
python code/slm_show.py checker --hold 10         :: 1 像素棋盘 = 检验 1:1 最狠的图
python code/slm_show.py --file phase.npy --hold 30  :: 自定义 uint8 数组
python code/slm_show.py grating --bench 120       :: 测帧率
```

图案：`white` `black` `grating` `checker` `comb` `blaze` `frame`。

作为库使用：

```python
from slm_driver import SLM
import numpy as np

slm = SLM(monitor=1)      # 0 基显示器序号，1 = 第二块屏
W, H = slm.getSize()      # 1024, 768
slm.update(frame)         # uint8 (H,W) 或 (H,W,3)，任意线程可调，立即返回
slm.run()                 # 主线程跑 wx 事件循环（阻塞）
slm.close()               # 任意线程：关窗并退出循环
```

## 4. 为什么不用 slmpy 自己的窗口

slmpy 在**工作线程**里创建 wx 窗口，而 Windows 版 wxWidgets 要求 GUI 调用只在主线程。
实测结果：

- 每次重绘都打印 `wxThread::IsMain() failed ... only the main thread can process Windows messages`；
- `isImageLock=True` 时会一直等事件锁，实测直接卡死；
- `updateArray()` 签名里有个隐藏参数 `sleep=0.2`，所以默认每帧 205 ms（≈5 fps）。

`slm_driver.py` 改成 wx 主线程 + 帧泵线程（每个刷新周期把"最新一帧"交给 GUI 线程，
旧帧直接丢弃），实测：`apply()` 约 3.5 ms，整链路 ≈50 fps（屏幕 60 Hz）。
需要 slmpy 兼容接口时给 `slm_show.py` 加 `--legacy`。

## 5. 设备型号与已确认/未确认

型号：**大恒光电（DHC）GCI-770202**，透射式 TN 液晶空间光调制器（振幅/相位混合调制），
由 HDMI 当第二块显示器驱动。

### 实测确认（本机）

| 项目 | 实测值 |
| --- | --- |
| 分辨率 | 1024x768（`wx.Display` + 1 像素棋盘 1:1 验证） |
| 色深 | 32 bpp = 8 bit/通道 → 256 阶 |
| 刷新 | 60 Hz |
| 接口 | 本机走 HDMI（Windows 看到的是一块 1024x768 显示器）；无厂商 SDK |

### 标称参数（**二手来源**，需实测核对）

来自一份汇总材料（大恒 GCI-77 系列产品页/教学套件页），不是原厂数据手册：

| 项目 | 参数 |
| --- | --- |
| 像素间距 | 18 µm（0.9" 面板；1.3" 版本为 26 µm） |
| 靶面 | 1024x768 @ 0.9"（18 µm x 1024 = 18.4 mm × 13.8 mm，对角 23 mm ✓ 自洽） |
| 填充因子 | 67% |
| 工作波段 | 400–700 nm |
| 透过率 | 55% |
| 相位行程 | 最大液晶延迟 Γ ≈ 400 nm；532 nm 处标称 0–1.5π，400 nm 处约 2π，633 nm 处约 1.26π |
| 偏振 | 线偏振入射，偏振方向平行摩擦方向（0°）；纯相位不加检偏器，正交检偏即振幅调制 |
| 对比度 | 1000:1 @532 nm，2000:1 @633 nm |
| 响应 | 60 Hz 下 TN 灰阶切换典型 10–30 ms |

### 这些数字意味着什么

1. **在 532 nm 拿不到 2π**：Γ = 400 nm → φmax = 2π·400/532 ≈ 1.5π。要 2π 只能用 400 nm 附近，
   或接受相位范围不足带来的效率损失（PSF/波前设计时要把 2π 的相位图案按 1.5π 行程重标定）。
2. **8 bit → 相位步进** ≈ 1.5π/255 ≈ 0.006π @532 nm，量化误差可接受。
3. TN 液晶是偏振调制：若入射偏振没对准 0°，相位和振幅会混在一起，看起来像"相位不对"。
4. 灰阶—相位是强非线性（通常 S 形），**必须标定 LUT** 再上相位图案。
5. 文献经验：小图案按 4x4 单元对应 1 像素上采样，可减少整幅拉伸到 1024x768 时的失真
   （物理学报 74, 20250592）。

### 光源：大恒 GCI-060401 红光 LED（620±10 nm）

系列 GCI-0604 LED 光源：红光 GCI-060401 = 620±10 nm；同系列还有 589±10、528±10（060403）、
451±10、365–375、白光 440–670。输入 DC 5V，功率标称 1 W 或 3 W（渠道口径不一），
发散角 120°，强度可调。

在 620 nm 处：

| 量 | 值 | 怎么来的 |
| --- | --- | --- |
| 相位行程 | φmax ≈ 1.29π（4.05 rad） | 2π·400/620 |
| 8 bit 相位步进 | ≈ 0.016 rad（≈0.005π） | φmax/255 |
| 谱宽引起的相位模糊 | ≈ 0.13 rad（≈0.04π） | φmax·Δλ/λ，整带 20 nm |
| 相干长度 | ≈ 19 µm | λ²/Δλ = 0.62²/0.02（µm²/µm） |

**三个后果：**

1. **必须加起偏器**。LED 是不偏振的，而 TN 液晶只调制平行于摩擦方向那一个偏振分量；
   不先起偏，另一半光原样透过去，对比度掉一半，看上去像"调制不深"。
2. **相位做不满 2π**。620 nm 只有 1.29π，相位图案要按 1.29π 归一化，否则效率损失。
3. **谱宽影响可忽略**（0.04π），但相干长度只有 ~19 µm，**不能用它做干涉/衍射标定**：
   测像素间距要用激光（He-Ne 633 / 532）。LUT 必须在 620 nm 上标定，灰阶—相位曲线随波长变。

### 待实测的两件事

- **像素间距**：加载 2 像素周期光栅，测一级衍射角 θ = arcsin(λ/p)；p = 36.6 µm（18 µm 版）、
  λ = 633 nm 时 θ ≈ 0.99°，26 µm 版（p = 52 µm）是 0.70°，容易分辨。**需激光，不能用 LED。**
- **相位行程与 LUT**：闪耀光栅 ±1 级衍射效率随灰阶的曲线（或干涉仪）反推相位曲线。

## 6. 把 SLM 当透镜用（`slm_lens.py`）

```cmd
python code/slm_lens.py --f 600 --hold 30        :: 会聚透镜，焦距 600 mm
python code/slm_lens.py --f 600 --diag           :: 只算不显示，打印设计诊断
python code/slm_lens.py --f 800 --save l800.npy  :: 存成数组
```

相位图 `phi(r) = -pi r^2/(lambda f)`，按 2pi 取模（菲涅尔），再线性映射到 8 bit。

620 nm 时面板只有 1.29pi 行程（alpha = 0.645）：焦点效率约 65%，另有约 20% 直穿成
零级亮斑——换 f 时这个亮斑**不会跟着动**，是判断"焦点是否真的形成"的关键对照。
换成 451 nm 蓝光 LED（GCI-060404）时 alpha = 0.887，焦点效率升到约 96%，零级只剩 2%，
这是这块面板做衍射器件时最值得换的一个参数。

设计边界：要求单像素相位差不超过 pi，即 r <= lambda*f/(2p)。18 um 间距、620 nm 下
全口径要用到 f >= 约 400 mm；f 更短就只有中心一圈在工作（等效缩小口径，焦斑变大）。
有效数值孔径 NA ~ lambda/(2p) ~ 0.017，所以这枚"透镜"很弱：f/# >= 29，
焦斑直径 40-70 um。它模拟的是"低 NA 透镜"，不是普通照相镜头。

诊断输出包含：有效口径、f/#、菲涅尔环数、边缘采样（周期/像素）、焦点效率、
零级份额、艾里半径。

### 用针孔 + Basler 验证的步骤

1. 针孔挡在 LED 前当点源，针孔到 SLM 距离记作 d，SLM 到相机距离记作 s。
2. 先打 `--f 600`，把相机放在 s 约 600 mm 附近（平行光入射时焦平面就在 f 处）；
   若针孔距 SLM 有限远 d，实际会聚点在 `1/s = 1/f - 1/d`。
3. 沿光轴前后移动相机，找"点变成最小"的位置；同时观察零级直穿斑（不动的那坨）作对照。
4. 依次换 f = 400 / 600 / 800 mm，会聚点距离应按设计值成比例变化。
5. 相机曝光手动锁定，曝光时间取 16.7 ms 的整数倍（或远大于它）避免拍到两个图案的混合。


## 6.5 随机透镜阵列（`random_lens_array.py`）

一堆位置随机、焦距也各不相同的微透镜（默认 80 枚，f = 30-50 mm），铺满整块面板。
每枚透镜的相位还是 `phi = -pi r^2/(lambda f)` 按 2pi 取模，外面是 0 相位（gray 0）。

```cmd
python code/random_lens_array.py --diag                  :: 只算，打印参数表 + 自检
python code/random_lens_array.py --show --hold 30        :: 显示到 SLM 30 s
python code/random_lens_array.py --save rla --show       :: 存 npy/png/csv 并显示
python code/random_lens_array.py --n 100 --seed 7        :: 换一版布局
```

输出（`--save` 前缀 `rla`）：

| 文件 | 内容 |
| --- | --- |
| `rla_phase.npy` | 1024x768 uint8，**直接送 SLM 的精确图案** |
| `rla_phase.png` | 同一图案的 1:1 PNG |
| `rla_preview.png` | 4x 超采样 + 复振幅盒式平均的抗锯齿预览（只用于看图） |
| `rla_lenses.csv` | 每枚透镜的 cx/cy/r/f/f#/环数/边缘采样 |

### 为什么短焦透镜必然小

采样极限：单像素相位差 `dphi/dr * p <= pi`，即 `r <= lambda*f/(2p)`。
18 um / 620 nm 下：f=30 mm 时 r ≤ 29 px（D ≤ 0.52 mm），f=50 mm 时 r ≤ 48 px
（D ≤ 1.72 mm）。所以焦距越短，透镜口径越小，也越少环数——这不是排版选择，
是面板像素间距定死的。脚本按 `--alias-frac`（默认 0.95）自动把半径夹在极限内，
不会画出混叠的环。

推论：这块面板上 f=3-5 cm 的透镜 NA ≤ 0.02，焦斑约 36 um（≈2 px），
它模拟的是"低 NA 随机透镜阵列"，不是照相镜头那种透镜阵列。

### 和参考图的差别

参考图里每枚透镜有 8-10 个宽环，是因为它的像素/焦距比例更大（环带更宽）。
在 18 um 面板上做 3-5 cm 焦距，最外圈环带只有 1-2 px 宽，相位锯齿必然是像素级的：
`rla_preview.png` 用复振幅平均做了抗锯齿，看得很平滑；但 SLM 上真实显示的就是
1:1 的锯齿环，这是物理采样，不是图案做错了。

### 两个和窗口有关的小事

- 只有加 `--show` 才开 SLM 窗口；`--diag`/`--save` 不会开，画面尺寸默认取本面板原生
  1024x768（面板换了就 `--w/--h` 或直接 `--show`）。
- 脚本里用模块级 `_KEEPALIVE` 压住了 `SLM` 对象：如果让它随 `main()` 返回就析构，
  wx 收尾顺序会让进程以 **127** 退出（图案和自检都正常，只是退出码错）。`slm_lens.py`
  还有同样的写法，批处理里如果用 `&&` 串命令要留意。

## 7. 测 PSF 到重建：完整流程

透射光路：

    LED(620nm) -> 针孔(<=15um) --d=40mm--> SLM --s=40mm--> Basler daA3840-45um

三条硬要求（比调参重要）：

1. SLM 的像素窗要遮光，只让有效口径的光过——否则相机拍到的全是绕射过边框的环境光；
2. 针孔压在光轴上，光斑落在靶面中心；
3. d 和 s 都量到各自平面中心，机械重现性好于 1 mm（NA=0.017，容差不小但也不大）。

针孔用 15 um 或更小。m = s/d = 1，物方分辨率 = 18 um，视场 = 7.72 x 4.36 mm
（bin 4 之后 8 um/pixel，相对 18 um 仍是 2.25x 过采样）。

### 7.1 采一组 PSF

    python code/psf_capture.py --out runs\psf01 --auto --n 32 --frames 16 --bin 4 --seed 0 --z-mm 40 --d-mm 40 --pinhole-um 15

`--auto` 会把曝光二分到 p99.9 落在 55% 满量程。`--frames 16` 平均降噪，
`--settle 0.15` 是换图后的等待（SLM 60 Hz，等 2 帧以上再曝，避免拍到半帧）。

### 7.2 先判数据能不能用

    python code/psf_check.py runs\psf01

看五项：饱和比例（>1% 就降曝光）、边缘/整体比（>0.9 说明 PSF 顶到靶面）、
质心漂移（>2 px 不稳）、两两相关（>0.95 说明掩模几乎一样）、有效秩
（90% 能量占几个奇异值，这才是真实独立测量数）。

### 7.3 采物：同一批掩模

把针孔换成待测物，其余不动，**`--seed` 必须一样**，掩模才会是同一批：

    python code/psf_capture.py --out runs\obj01 --n 32 --frames 16 --bin 4 --seed 0 --z-mm 40 --d-mm 40 --exposure-us 4000

`--exposure-us` 填 7.1 那次的 `meta.json` 里的值，省得物这轮曝光不一致。

### 7.4 重建

    python code/psf_recon.py --run runs\psf01 --obj runs\obj01\stack.npy --lam 0.01 --iters 300

模型是 `y_m = h_m ⊛ x + n_m`，联合解卷积 + TV 正则 + 非负约束，FISTA 迭代。

### 7.5 代码自检（不需要光路）

    python code/psf_recon.py --selftest runs\selftest

合成数据实测：直接平均基线 13.27 dB，重建 25.82 dB（+12.56 dB），
说明解卷积和 TV 这条链是通的。真实性能另说。

### 7.6 已知的物理短板

没有偏振片时，TN 面板只调制平行于摩擦方向的分量，另一半光原样透过，
所以 PSF 里混着未调制的背景；表现为 `psf_check.py` 的相关性偏高、有效秩偏低。
一片线偏振片（几十元，不要圆偏振 CP L）就能把这部分拿回来，是当前性价比最高的改进。


## 8. 排查清单（每一次实验开始前）

**第一件事：确认 SLM 的电源开关是打开的。**

2026-11-17 的整轮排查最后就是卡在这里：电源没开时——

- Windows 照样能枚举出 `\\.\DISPLAY2` 1024x768，窗口照常绘制、屏幕截图完全正常；
- 相机却拍不到任何调制（全黑/全白、prism 锯齿光栅、随机相位掩模，差异都在 0.1% 以下）；
- 盖住面板相机变黑（说明光确实从面板方向来），但显示黑不变暗（液晶没在切换）。

也就是"电学全对、光学全错"，只看软件侧永远查不出来。

判据（`align_diff.py`）：

```
max |white-black| > 2% FS      且      |diff| > 3% FS 的像素占比 > 1%
```

达不到就先去查电源、查信号线，别急着调光路。

## 9. 无偏振片时的共模去除（必用）

实测调制深度只有 **约 8%**：92% 的光没被液晶调制（无检偏器时，与液晶摩擦方向
正交的分量原样穿过），它对所有掩模都一样，是一层"共模"背景。

`psf_check.py` 和 `psf_recon.py` 都支持 `--cmsub`：把 32 张图的平均减掉再算。
数学上严格等价——共模项 `B` 对所有掩模相同，`y_m - mean(y) = (H_m - mean(H)) x`，
`B x` 被消掉，剩下的就是真正被调制的那部分。

实测（s=d=40 mm，bin4，32 张随机相位）：

| 指标 | 原始 | 去共模后 |
| --- | --- | --- |
| 两两相关 | 0.977（最大 0.980） | −0.032（最大 0.064） |
| 有效秩（90% 能量） | 1 / 32 | **27 / 32** |
| 结论 | 病态 | 可以重建 |

加一片线偏振片（放在 LED 与面板之间，透光轴对准液晶摩擦方向）能把 8% 提到接近
100%，等效信噪比提升一个数量级，是下一步最划算的硬件改进。

## 10. 脚本清单（全部在 `code/` 目录）

| 脚本 | 用途 |
| --- | --- |
| `slm_show.py` | 显示测试图（`--info` 看拓扑） |
| `slm_lens.py` | 菲涅尔透镜相位图案 + 设计诊断 |
| `random_lens_array.py` | 随机位置/随机焦距的微透镜阵列相位图（含自检） |
| `align_diff.py` | 黑/白逐像素差值，判定"有没有调制" |
| `align_scan.py` | 黑/白交替 + 相机读数，边挪面板边找对准 |
| `align_watch.py` | 只读相机读数（做遮挡实验用） |
| `cam_shot.py` | 抓一帧存 PNG，人眼看相机拍到了什么 |
| `cam_reset_roi.py` | 相机 ROI 是掉电保持的，跑测试前先清成全画幅 |
| `psf_capture.py` | 采 PSF / 物体图（掩模族：random/lens/flat/prism/shutter） |
| `psf_check.py` | 判定数据能不能重建（`--cmsub`） |
| `psf_recon.py` | FISTA + TV 联合重建（`--selftest` 自检、`--cmsub`） |
| `rank_test.py` | 看 PSF 集合在去共模前后的奇异值谱 |
| `diff_view.py` | 把差值的 npz 画成 PNG |
| `cam_stack.py` | 抓 N 帧求平均（`--exp/--n/--gain/--out`），打印 mean/p99.9/饱和/帧间噪声 |
| `dense_mla.py` | 六角密排微透镜阵列（按 `1/f=1/d+1/s` 定 f，`--area-mm` 定簇大小） |
| `hybrid_pattern.py` | 随机透镜阵列 + 随机相位背景（`--bg-max` 调背景调制深度） |
| `random_phase.py` | 逐像素随机相位（散斑），`--block` 可做块状随机相位 |
| `slm_plain.py` | 在面板上显示单色灰阶（`--grey 0` 做黑屏参考帧） |
| `lens_focal_sweep.py` | 已废弃：早期用 `slm_show.py --file` 逐窗口切换的焦距扫描 |
| `psf_scan2.py` | 单进程轴向 PSF 扫描（改 f 等效移焦，一次开窗一次开相机） |

## 11. 实测数据

`data/2026-11-17/` 是唯一入库的实验数据，详见 [data/README.md](data/README.md)：

| 子目录 | 内容 | 体积 |
| --- | --- | --- |
| `data/2026-11-17/raw/b_psf*` | PSF 采集、平场、差值 PSF（单张二元 0/π 掩模） | 13 MB |
| `data/2026-11-17/raw/e_bin`、`e_flat` | 32 张随机掩模的箭头物体采集 + 平场 | 70 MB |
| `data/2026-11-17/result/` | 结果包：`psf_d.npy`、`measure_32masks_minus_flat.npy`、箭头图、重建留档、光路照片，自带 README | 71 MB |

有效性判据（PSF 边缘/中心 0.313、掩模两两相关 ≈0、90% 能量 28/32 奇异值）和
失败案例的剔除理由都写在 `data/README.md` 里。本地实时采集仍写 `runs/`（不入库）。
