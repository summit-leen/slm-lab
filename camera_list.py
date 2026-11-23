# -*- coding: utf-8 -*-
"""列出所有 Basler 相机（型号、序列号、接口），并尽量读出传感器信息。"""
import sys

from pypylon import pylon

print('pypylon:', pylon.__version__)

tl = pylon.TlFactory.GetInstance()
devices = tl.EnumerateDevices()
print(f'发现 {len(devices)} 台设备')
for i, d in enumerate(devices):
    print(f'\n[{i}]')
    for name in ('GetFriendlyName', 'GetModelName', 'GetSerialNumber',
                 'GetDeviceClass', 'GetInterfaceID', 'GetFullName',
                 'GetUserDefinedName', 'GetVendorName'):
        try:
            print(f'    {name[3:]:18s} = {getattr(d, name)()}')
        except Exception as e:
            print(f'    {name[3:]:18s} = <{type(e).__name__}>')

if not devices:
    sys.exit(0)

print('\n=== 尝试打开并读取设备信息 ===')
for i, d in enumerate(devices):
    print(f'\n--- device[{i}] {d.GetModelName()} / {d.GetSerialNumber()}')
    cam = None
    try:
        cam = pylon.InstantCamera(tl.CreateDevice(d))
        cam.Open()
        info = cam.GetDeviceInfo()
        for attr in ('GetModelName', 'GetSerialNumber', 'GetDeviceVersion',
                     'GetDeviceClass', 'GetUserDefinedName', 'GetVendorName'):
            try:
                print(f'    {attr[3:]:18s} = {getattr(info, attr)()}')
            except Exception as e:
                print(f'    {attr[3:]:18s} = <{type(e).__name__}>')
        for node in ('Width', 'Height', 'WidthMax', 'HeightMax', 'PixelSize',
                     'SensorWidth', 'SensorHeight', 'PixelFormat'):
            try:
                print(f'    node {node:12s} = {getattr(cam, node).Value}')
            except Exception as e:
                print(f'    node {node:12s} = <{type(e).__name__}>')
    except Exception as e:
        print('    打开失败:', type(e).__name__, e)
    finally:
        if cam is not None:
            try:
                if cam.IsOpen():
                    cam.Close()
            except Exception:
                pass
