# -*- coding: utf-8 -*-
"""把实物光路照片写进工作日志（替换/新增相关段落）。"""
import io
import os

ROOT = os.path.dirname(os.path.abspath(__file__))
MD = os.path.join(ROOT, "2026-11-17-SLM工作日志.md")

with io.open(MD, "r", encoding="utf-8") as f:
    text = f.read()

# 1) §1 硬件表后面插入照片（相对路径，md 与 result 文件夹同级）
anchor = "### 分辨率的硬约束（本日最重要的公式）"
photo_block = u"""### 实物光路照片

![实物光路](result_20261117/setup_photo.jpg)

绝对路径：`D:\\课题组\\slm\\result_20261117\\setup_photo.jpg`（1279×1706，手机竖拍）

画面里能认出的东西：**GCI-060401 红光 LED**（下方，可见红光）→ 包了黑胶带的遮光筒 → **GCI-770202 SLM 面板**（左上方贴胶带的黑盒子）→ 相机（在画面外）。平台是 Thorlabs 光学平板，SLM 与 LED 都用支杆和压块固定。

"""
assert anchor in text
text = text.replace(anchor, photo_block + anchor, 1)

# 2) §9.1 第 3 页的配图改成实物照
old_row = u"| 3 | 硬件与几何 | 无（用表格） | LED 620 nm → 100 µm 孔 → d=50 mm → SLM → s=40 mm → 相机 |"
new_row = u"| 3 | 硬件与几何 | `setup_photo.jpg` | LED 620 nm → 100 µm 孔 → d=50 mm → SLM → s=40 mm → 相机 |"
assert old_row in text
text = text.replace(old_row, new_row, 1)

# 3) §9.2 表格加一行
old2 = u"| `D:\\课题组\\slm\\result_20261117\\slm_lens_screenshot.jpg` | 1024×768 | 菲涅尔透镜图案（f=150、tilt 0.10）在 SLM 上的截图 |"
new2 = old2 + u"\n| `D:\\课题组\\slm\\result_20261117\\setup_photo.jpg` | 1279×1706 | **实物光路照片**：LED + 遮光筒 + SLM 面板 + 光学平台 |"
assert old2 in text
text = text.replace(old2, new2, 1)

# 4) §9.5 去掉"缺照片"那条
old3 = u"- **缺一张光路实物照**：今日没有拍设备照片，做 PPT 时第 3 页只能用文字流程图代替；如需照片需补拍。"
new3 = u"- 实物光路照片已补齐（`result_20261117\\setup_photo.jpg`），第 3 页可直接用；照片是竖拍，PPT 里裁成 4:3 或竖栏更合适。"
assert old3 in text
text = text.replace(old3, new3, 1)

# 5) §8 文件树补一行
old4 = u"│   ├── slm_lens_screenshot.jpg"
new4 = u"│   ├── slm_lens_screenshot.jpg\n│   ├── setup_photo.jpg                    ← 实物光路照片"
assert old4 in text
text = text.replace(old4, new4, 1)

# 6) 结果包文件数 14 -> 15
text = text.replace(u"（14 个文件 + README）", u"（15 个文件 + README）")

with io.open(MD, "w", encoding="utf-8") as f:
    f.write(text)

print("patched:", MD)
print("size:", os.path.getsize(MD))
