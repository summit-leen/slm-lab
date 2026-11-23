# -*- coding: utf-8 -*-
from pypylon import pylon

tlf = pylon.TlFactory.GetInstance()
cam = pylon.InstantCamera(tlf.CreateDevice(tlf.EnumerateDevices()[0]))
cam.Open()
for name in ("PixelSize", "SensorWidth", "SensorHeight", "WidthMax", "HeightMax",
             "BslPixelSize", "DeviceModelName", "RecommendedPixelSize"):
    try:
        node = getattr(cam, name)
        print(name, node.GetValue() if hasattr(node, "GetValue") else node)
    except Exception as exc:
        print(name, "n/a", type(exc).__name__)
cam.Close()
