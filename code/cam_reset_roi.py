# -*- coding: utf-8 -*-
"""把 Basler 相机恢复成全画幅（清掉上一次运行留下的 ROI/binning）。

相机的 ROI 设置是**掉电保持**的：上一次测试用了 1600x1200 的中心窗口，
之后每次打开相机都还在那个窗口里，只有 3.2x2.4 mm 的视场。
"""
from __future__ import annotations

import sys

from pypylon import pylon

tlf = pylon.TlFactory.GetInstance()
devs = tlf.EnumerateDevices()
if not devs:
    raise SystemExit("没找到相机")
cam = pylon.InstantCamera(tlf.CreateDevice(devs[0]))
cam.Open()
print("model:", cam.GetDeviceInfo().GetModelName())

for node in ("BinningHorizontal", "BinningVertical"):
    try:
        getattr(cam, node).SetValue(1)
    except Exception as exc:
        print(node, "->", exc)

try:
    cam.OffsetX.SetValue(0)
    cam.OffsetY.SetValue(0)
except Exception as exc:
    print("offset ->", exc)
try:
    cam.Width.SetValue(cam.WidthMax.GetValue())
    cam.Height.SetValue(cam.HeightMax.GetValue())
except Exception as exc:
    print("size ->", exc)

print(f"width={cam.Width.GetValue()} height={cam.Height.GetValue()} "
      f"offset=({cam.OffsetX.GetValue()},{cam.OffsetY.GetValue()}) "
      f"bin={cam.BinningHorizontal.GetValue()}")
cam.Close()
sys.stdout.flush()
