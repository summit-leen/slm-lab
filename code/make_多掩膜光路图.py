# -*- coding: utf-8 -*-
"""
基于可编程 SLM 的多掩膜无镜成像光路 - 技术示意图
按《多掩膜光路图-绘制说明.md》v1 规格逐条绘制，坐标单位 = 画布像素 (3200 x 1800)
"""
import math
import random
from PIL import Image, ImageDraw, ImageFont

# ---------------- 基础参数 ----------------
S = 2                      # 超采样倍数（2 倍绘制后 LANCZOS 缩放，保证细线质量）
W, H = 3200, 1800
AX = 900                   # 光轴 y

PNG_OUT = r"D:\课题组\slm\多掩膜光路图.png"
SVG_OUT = r"D:\课题组\slm\多掩膜光路图.svg"

INK = (32, 33, 36)
GRAY = (95, 99, 104)
LMID = (154, 160, 166)
EDGE = (60, 64, 67)
LIGHT = (232, 234, 237)
SHADE = (208, 212, 216)
DARK = (43, 43, 43)
CARD = (26, 26, 26)
RED = (229, 57, 53)
BLUE = (26, 115, 232)
GREEN = (46, 125, 50)
ORANGE = (232, 89, 12)
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)

FONTS = {False: r"C:\Windows\Fonts\msyh.ttc", True: r"C:\Windows\Fonts\msyhbd.ttc"}
_fc = {}


def F(size, bold=False):
    k = (int(round(size * S)), bold)
    if k not in _fc:
        _fc[k] = ImageFont.truetype(FONTS[bold], k[0])
    return _fc[k]


img = Image.new("RGBA", (W * S, H * S), (255, 255, 255, 255))
ov = Image.new("RGBA", (W * S, H * S), (0, 0, 0, 0))
d = ImageDraw.Draw(img)
do = ImageDraw.Draw(ov)
SVG = []


def hx(c):
    return "#%02X%02X%02X" % c


# ---------------- 绘图原子 ----------------
def line(x1, y1, x2, y2, color=EDGE, w=1.5, a=255, dash=None, tg="main"):
    dd = d if tg == "main" else do
    col = color + (a,)
    if dash is None:
        dd.line([x1 * S, y1 * S, x2 * S, y2 * S], fill=col, width=max(1, int(round(w * S))))
        SVG.append(dict(t="line", x1=x1, y1=y1, x2=x2, y2=y2, c=hx(color), w=w, o=a / 255.0))
    else:
        L = math.hypot(x2 - x1, y2 - y1)
        if L < 0.5:
            return
        step = dash + dash * 0.75
        s = 0.0
        while s < L:
            e = min(s + dash, L)
            ax, ay = x1 + (x2 - x1) * s / L, y1 + (y2 - y1) * s / L
            bx, by = x1 + (x2 - x1) * e / L, y1 + (y2 - y1) * e / L
            dd.line([ax * S, ay * S, bx * S, by * S], fill=col, width=max(1, int(round(w * S))))
            s += step
        SVG.append(dict(t="line", x1=x1, y1=y1, x2=x2, y2=y2, c=hx(color), w=w,
                        o=a / 255.0, dash=(dash, dash * 0.75)))


def poly(pts, fill=None, stroke=None, w=1.5, af=255, as_=255, tg="main"):
    dd = d if tg == "main" else do
    xy = [(x * S, y * S) for x, y in pts]
    if fill is not None:
        dd.polygon(xy, fill=fill + (af,))
    if stroke is not None:
        dd.line(xy + [xy[0]], fill=stroke + (as_,), width=max(1, int(round(w * S)))
                , joint="curve")
    SVG.append(dict(t="poly", p=pts, f=hx(fill) if fill else None, fo=af / 255.0,
                    s=hx(stroke) if stroke else None, sw=w, so=as_ / 255.0))


def rect(x0, y0, x1, y1, fill=None, stroke=None, w=2, r=0, af=255, as_=255, tg="main"):
    dd = d if tg == "main" else do
    box = [x0 * S, y0 * S, x1 * S, y1 * S]
    wpx = max(1, int(round(w * S)))
    if fill is not None:
        if r:
            dd.rounded_rectangle(box, radius=r * S, fill=fill + (af,))
        else:
            dd.rectangle(box, fill=fill + (af,))
    if stroke is not None:
        if r:
            dd.rounded_rectangle(box, radius=r * S, outline=stroke + (as_,), width=wpx)
        else:
            dd.rectangle(box, outline=stroke + (as_,), width=wpx)
    SVG.append(dict(t="rect", x0=x0, y0=y0, x1=x1, y1=y1, r=r,
                    f=hx(fill) if fill else None, fo=af / 255.0,
                    s=hx(stroke) if stroke else None, sw=w, so=as_ / 255.0))


def ellipse(cx, cy, rx, ry, fill=None, stroke=None, w=1.5, af=255, as_=255, tg="main"):
    dd = d if tg == "main" else do
    box = [(cx - rx) * S, (cy - ry) * S, (cx + rx) * S, (cy + ry) * S]
    if fill is not None:
        dd.ellipse(box, fill=fill + (af,))
    if stroke is not None:
        dd.ellipse(box, outline=stroke + (as_,), width=max(1, int(round(w * S))))
    SVG.append(dict(t="ell", cx=cx, cy=cy, rx=rx, ry=ry,
                    f=hx(fill) if fill else None, fo=af / 255.0,
                    s=hx(stroke) if stroke else None, sw=w, so=as_ / 255.0))


def text(x, y, s, size=18, color=INK, bold=False, anchor="mm", a=255, tg="main"):
    dd = d if tg == "main" else do
    dd.text((x * S, y * S), s, font=F(size, bold), fill=color + (a,), anchor=anchor)
    amap = {"mm": ("middle", "middle"), "lm": ("start", "middle"),
            "rm": ("end", "middle"), "ct": ("middle", "top")}
    SVG.append(dict(t="text", x=x, y=y, s=s, size=size, c=hx(color), o=a / 255.0,
                    a=anchor, bold=bold))


# ---------------- 尺寸标注 ----------------
def arrow_h(x, y, direction, color=BLUE, L=9, hw=3.4):
    poly([(x, y), (x + direction * L, y - hw), (x + direction * L, y + hw)],
         fill=color, stroke=None)


def dim_h(x1, x2, y, label, size=20, tdy=28, ext_from=None, color=BLUE, labelsize=None):
    line(x1, y, x2, y, color, 1.5)
    arrow_h(x1, y, -1, color)
    arrow_h(x2, y, +1, color)
    if ext_from:
        for xx, y0 in ext_from:
            line(xx, y0, xx, y - 5, (218, 220, 224), 1.0, dash=5)
    text((x1 + x2) / 2.0, y + tdy, label, size if labelsize is None else labelsize, color, anchor="mm")


# =========================================================
# 1. 光束（半透明红，位于最底层）
# =========================================================
BEAM_FILL_A = 64      # 25% 不透明

# LED -> 针孔（收拢锥）
poly([(280, 880), (280, 920), (429, 900)], fill=RED, stroke=RED, w=1.5,
     af=BEAM_FILL_A, as_=255, tg="ov")

# 针孔 -> 物面卡（发散锥，被断轴分为两段）
H_CARD = 72.0
def half_at(x):
    return H_CARD * (x - 430) / (1560 - 430)

poly([(430, 900), (950, AX - half_at(950)), (950, AX + half_at(950))],
     fill=RED, stroke=RED, w=1.5, af=BEAM_FILL_A, tg="ov")
poly([(1150, AX - half_at(1150)), (1560, AX - H_CARD), (1560, AX + H_CARD),
      (1150, AX + half_at(1150))],
     fill=RED, stroke=RED, w=1.5, af=BEAM_FILL_A, tg="ov")

# 物面卡 -> SLM（细锥，仅孔位置透光）
poly([(1563, 893), (1940, 874), (1940, 926), (1563, 907)],
     fill=RED, stroke=RED, w=1.5, af=BEAM_FILL_A, tg="ov")

# SLM -> 相机（带散斑）
poly([(2060, 873), (2416, 858), (2416, 942), (2060, 927)],
     fill=RED, stroke=RED, w=1.5, af=BEAM_FILL_A, tg="ov")

# 散斑纹理（末段）
rng = random.Random(20261118)
n_dots = 430
for _ in range(n_dots):
    x = rng.uniform(2068, 2408)
    t = (x - 2060) / 356.0
    top = 873 - 21 * t
    bot = 927 + 21 * t
    y = rng.uniform(top + 6, bot - 6)
    r = rng.choice([1.0, 1.0, 1.2, 1.5, 1.8])
    a = rng.randint(70, 160)
    ellipse(x, y, r, r, fill=(200, 40, 36), af=a, tg="ov")

# 少量更亮的散斑核
for _ in range(8):
    x = rng.uniform(2100, 2390)
    t = (x - 2060) / 356.0
    top = 873 - 21 * t
    bot = 927 + 21 * t
    y = rng.uniform(top + 12, bot - 12)
    ellipse(x, y, 2.6, 2.6, fill=(150, 22, 20), af=200, tg="ov")

img.alpha_composite(ov)
ov = Image.new("RGBA", (W * S, H * S), (0, 0, 0, 0))
do = ImageDraw.Draw(ov)

# =========================================================
# 2. 元件
# =========================================================
# ---- 2.1 LED ----
rect(160, 878, 280, 922, fill=WHITE, stroke=None)
rect(160, 913, 280, 922, fill=SHADE, stroke=None)
rect(268, 878, 272, 922, fill=(224, 227, 230), stroke=None)
rect(160, 878, 280, 922, fill=None, stroke=(154, 160, 166), w=2, r=6)
ellipse(163, 900, 4, 21, fill=WHITE, stroke=(154, 160, 166), w=1.6)
line(158, 886, 126, 872, (200, 60, 60), 1.6)       # 红线
line(158, 914, 126, 928, (60, 60, 60), 1.6)        # 黑线
ellipse(274, 900, 5, 5, fill=ORANGE, stroke=None)

text(214, 898, "红光 LED", 17, INK, anchor="mm")
text(220, 846, "LED 620 nm", 18, INK)
text(220, 940, "GCI-060401", 15, GRAY)
line(220, 862, 220, 874, LMID, 1.0, dash=6)

# ---- 2.2 针孔片 ----
rect(428, 875, 432, 925, fill=LIGHT, stroke=EDGE, w=1.5)
ellipse(430, 900, 1.6, 1.6, fill=BLACK, stroke=None)
line(430, 875, 430, 853, LMID, 1.0, dash=6)
line(430, 925, 430, 939, LMID, 1.0, dash=6)
text(430, 840, "Ø100 µm 针孔", 18, INK)
text(430, 952, "相干源", 16, GRAY)

# ---- 2.3 断轴 ----
line(950, AX, 1016, AX, EDGE, 2)
line(1076, AX, 1150, AX, EDGE, 2)
line(1019, AX + 26, 1039, AX - 26, EDGE, 2)
line(1049, AX + 26, 1069, AX - 26, EDGE, 2)
text(1030, 826, "480 mm", 22, INK, bold=True, anchor="rm")
text(1036, 828, "（示意，非等比）", 15, GRAY, anchor="lm")

# ---- 2.4 物面卡 ----
rect(1557, 840, 1563, 960, fill=CARD, stroke=CARD, w=1)
# 箭头镂空（朝上，14 x 12，放大示出）
poly([(1560, 886), (1553.5, 902), (1566.5, 902)], fill=WHITE, stroke=None)
# 标定孔
ellipse(1563, 918, 1.6, 1.6, fill=WHITE, stroke=None)
line(1564.5, 916, 1612, 866, LMID, 1.0)
text(1620, 862, "标定孔 Ø150 µm（放大示出，右距 12 mm）", 15, GRAY, anchor="lm")

line(1560, 840, 1560, 776, LMID, 1.0, dash=6)
text(1560, 762, "物面卡 60×60 mm", 18, INK)

text(1560, 1044, "箭头 3 mm（透过率图案）", 16, INK)
text(1560, 1076, "标定孔 Ø150 µm（放大示出）", 16, INK)
text(1560, 1108, "两孔间隔 12 mm", 16, INK)

# ---- 2.5 SLM ----
rect(1940, 845, 2060, 955, fill=LIGHT, stroke=(95, 99, 104), w=2, r=4)
# 有效面板 70 x 53
rect(1942, 873, 2012, 926, fill=DARK, stroke=(70, 70, 70), w=1)
# 像素网格
for gx in range(1946, 2012, 4):
    line(gx, 874, gx, 925, (74, 74, 74), 0.8)
for gy in range(877, 926, 4):
    line(1943, gy, 2011, gy, (74, 74, 74), 0.8)
rect(1942, 873, 2012, 926, fill=None, stroke=(120, 124, 128), w=1)

# 线缆
line(2058, 858, 2118, 802, LMID, 1.3)
line(2058, 878, 2100, 824, LMID, 1.3)
text(2122, 798, "HDMI", 12, GRAY, anchor="lm")
text(2104, 828, "DC", 12, GRAY, anchor="lm")

# 标注（靠上，四行）
line(1977, 873, 1977, 802, LMID, 1.0, dash=6)
text(2000, 790, "GCI-770202", 15, GRAY)
text(2000, 758, "像素 18 µm ｜ 相位型", 18, INK)
text(2000, 726, "SLM 1024×768", 18, INK)
text(2000, 694, "有效面板 18.43 × 13.82 mm", 18, INK)

# ---- 2.6 相机 ----
rect(2416, 864, 2503, 936, fill=WHITE, stroke=GREEN, w=2, r=3)
rect(2418, 886, 2466, 913, fill=(26, 26, 26), stroke=None)
rect(2466, 886, 2468, 913, fill=(90, 90, 90), stroke=None)
# 芯片与接口
rect(2472, 870, 2484, 882, fill=(32, 32, 32), stroke=None)
rect(2486, 916, 2498, 928, fill=(32, 32, 32), stroke=None)
rect(2492, 870, 2500, 878, fill=(70, 70, 70), stroke=None)
rect(2496, 898, 2503, 908, fill=(120, 124, 128), stroke=(60, 64, 67), w=1)

line(2460, 864, 2460, 796, LMID, 1.0, dash=6)
text(2460, 782, "相机（裸靶面）", 18, INK)
text(2460, 750, "裸靶面 7.72 × 4.36 mm", 18, INK)
text(2460, 720, "Basler daA3840-45um", 15, GRAY)

# =========================================================
# 3. 尺寸标注
# =========================================================
dim_h(283, 427, 985, "5 mm", 20, ext_from=[(283, 922), (427, 925)])
dim_h(1572, 1936, 985, "30 mm", 20, ext_from=[(1572, 960), (1936, 955)])
dim_h(2066, 2410, 985, "40 mm", 20, ext_from=[(2066, 955), (2410, 936)])

text(2160, 874, "散斑 1.38 mm", 15, (120, 58, 54))

# =========================================================
# 4. 标题
# =========================================================
text(1600, 112, "基于可编程 SLM 的多掩膜无镜成像光路", 42, INK, bold=True)

# =========================================================
# 5. Inset A：物面卡正视图
# =========================================================
text(540, 1196, "Inset A｜物面卡（正面）", 22, INK, bold=True)
rect(364, 1259, 716, 1611, fill=WHITE, stroke=(189, 189, 189), w=1)
rect(370, 1265, 710, 1605, fill=CARD, stroke=None)
# 箭头 3 mm = 17 px（放大示出）
poly([(540, 1427), (533.5, 1444.5), (546.5, 1444.5)], fill=WHITE, stroke=None)
# 标定孔（放大示出）
ellipse(608, 1435, 5, 5, fill=None, stroke=(200, 204, 208), w=1)
ellipse(608, 1435, 2.2, 2.2, fill=WHITE, stroke=None)
# 12 mm 尺寸
line(540, 1449, 540, 1615, (110, 114, 118), 1, dash=5)
line(608, 1442, 608, 1615, (110, 114, 118), 1, dash=5)
line(540, 1617, 608, 1617, BLUE, 1.5)
arrow_h(540, 1617, -1)
arrow_h(608, 1617, +1)
text(574, 1638, "12 mm", 14, BLUE)
text(506, 1436, "3 mm", 14, (200, 204, 208), anchor="rm")
text(620, 1426, "Ø150 µm", 12, (200, 204, 208), anchor="lm")
text(392, 1582, "60 × 60 mm", 14, (150, 154, 158), anchor="lm")

# =========================================================
# 6. Inset B：靶面散斑
# =========================================================
text(2560, 1316, "Inset B｜靶面散斑（32 掩模之一）", 22, INK, bold=True)
BX0, BY0, BX1, BY1 = 2320, 1364, 2800, 1635
rect(BX0, BY0, BX1, BY1, fill=(24, 24, 24), stroke=(70, 70, 70), w=1)

rng2 = random.Random(77138)
for _ in range(72):
    x = rng2.uniform(BX0 + 10, BX1 - 10)
    y = rng2.uniform(BY0 + 10, BY1 - 10)
    r = rng2.uniform(1.4, 2.6)
    a = rng2.randint(150, 245)
    ellipse(x, y, r, r, fill=WHITE, af=a)

# 视场虚线框 5.8 x 3.3 mm
FX0, FX1 = 2379.5, 2740.5
FY0, FY1 = 1392.5, 1597.5
for (a, b, c, e) in [(FX0, FY0, FX1, FY0), (FX0, FY1, FX1, FY1),
                     (FX0, FY0, FX0, FY1), (FX1, FY0, FX1, FY1)]:
    line(a, b, c, e, (170, 174, 178), 1.2, dash=8)

# 单散斑 1.38 mm 虚线圆
CCX, CCY, CR = 2640, 1476, 43
steps = 60
for i in range(steps):
    if i % 2:
        continue
    a0 = 2 * math.pi * i / steps
    a1 = 2 * math.pi * (i + 1) / steps
    line(CCX + CR * math.cos(a0), CCY + CR * math.sin(a0),
         CCX + CR * math.cos(a1), CCY + CR * math.sin(a1), (255, 255, 255), 1.4)
text(2580, 1476, "1.38 mm", 13, (235, 235, 235), anchor="rm")

# 分辨率 1.03 mm 标尺
line(2380, 1616, 2444, 1616, (235, 235, 235), 1.4)
line(2380, 1610, 2380, 1622, (235, 235, 235), 1.4)
line(2444, 1610, 2444, 1622, (235, 235, 235), 1.4)
text(2452, 1616, "1.03 mm", 13, (235, 235, 235), anchor="lm")

text(2320, 1662, "视场 5.8 × 3.3 mm（虚线框）", 14, GRAY, anchor="lm")

# =========================================================
# 7. 右下角指标
# =========================================================
text(2872, 1364, "关键指标", 15, GRAY, bold=True, anchor="lm")
line(2872, 1380, 2872, 1516, BLUE, 2)
metrics = ["视场 5.8 × 3.3 mm", "分辨率 1.03 mm", "散斑 1.38 mm", "相干长度 3 mm"]
for i, s in enumerate(metrics):
    text(2890, 1396 + i * 36, s, 17, INK, anchor="lm")

# =========================================================
# 保存
# =========================================================
img.convert("RGB").resize((W, H), Image.LANCZOS).save(PNG_OUT, dpi=(300, 300), optimize=True)


# ---------------- SVG ----------------
def svg_text(op):
    s = op["s"].replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    anchor = {"mm": "middle", "lm": "start", "rm": "end", "ct": "middle"}[op["a"]]
    y = op["y"] + op["size"] * 0.34
    fw = ' font-weight="bold"' if op["bold"] else ""
    return ('<text x="%.1f" y="%.1f" font-family="Microsoft YaHei, 微软雅黑, sans-serif" '
            'font-size="%.1f" fill="%s" fill-opacity="%.2f" text-anchor="%s"%s>%s</text>'
            % (op["x"], y, op["size"], op["c"], op["o"], anchor, fw, s))


parts = ['<?xml version="1.0" encoding="UTF-8"?>',
         '<svg xmlns="http://www.w3.org/2000/svg" width="3200" height="1800" '
         'viewBox="0 0 3200 1800">',
         '<rect x="0" y="0" width="3200" height="1800" fill="#FFFFFF"/>']
for op in SVG:
    t = op["t"]
    if t == "line":
        dash = ' stroke-dasharray="%.1f %.1f"' % op["dash"] if op.get("dash") else ""
        parts.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="%s" '
                     'stroke-width="%.1f" stroke-opacity="%.2f"%s/>'
                     % (op["x1"], op["y1"], op["x2"], op["y2"], op["c"], op["w"], op["o"], dash))
    elif t == "poly":
        pts = " ".join("%.1f,%.1f" % (x, y) for x, y in op["p"])
        f = (' fill="%s" fill-opacity="%.2f"' % (op["f"], op["fo"])) if op["f"] else ' fill="none"'
        s = (' stroke="%s" stroke-width="%.1f" stroke-opacity="%.2f"' % (op["s"], op["sw"], op["so"])
             if op["s"] else "")
        parts.append('<polygon points="%s"%s%s/>' % (pts, f, s))
    elif t == "rect":
        f = (' fill="%s" fill-opacity="%.2f"' % (op["f"], op["fo"])) if op["f"] else ' fill="none"'
        s = (' stroke="%s" stroke-width="%.1f" stroke-opacity="%.2f"' % (op["s"], op["sw"], op["so"])
             if op["s"] else "")
        rr = ' rx="%.1f" ry="%.1f"' % (op["r"], op["r"]) if op["r"] else ""
        parts.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f"%s%s%s/>'
                     % (op["x0"], op["y0"], op["x1"] - op["x0"], op["y1"] - op["y0"], rr, f, s))
    elif t == "ell":
        f = (' fill="%s" fill-opacity="%.2f"' % (op["f"], op["fo"])) if op["f"] else ' fill="none"'
        s = (' stroke="%s" stroke-width="%.1f" stroke-opacity="%.2f"' % (op["s"], op["sw"], op["so"])
             if op["s"] else "")
        parts.append('<ellipse cx="%.1f" cy="%.1f" rx="%.1f" ry="%.1f"%s%s/>'
                     % (op["cx"], op["cy"], op["rx"], op["ry"], f, s))
    elif t == "text":
        parts.append(svg_text(op))
parts.append("</svg>")

with open(SVG_OUT, "w", encoding="utf-8") as fp:
    fp.write("\n".join(parts))

print("PNG:", PNG_OUT)
print("SVG:", SVG_OUT, "ops=", len(SVG))
