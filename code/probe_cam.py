# -*- coding: utf-8 -*-
"""相机连通性探针：打开第一台 Basler，打印信息，抓若干帧看亮度。"""
import sys
import numpy as np
from pypylon import pylon

def main() -> int:
    tlf = pylon.TlFactory.GetInstance()
    devs = tlf.EnumerateDevices()
    print(f"found {len(devs)} device(s)")
    if not devs:
        return 1
    cam = pylon.InstantCamera(tlf.CreateDevice(devs[0]))
    cam.Open()
    print("model      ", cam.GetDeviceInfo().GetModelName())
    print("serial     ", cam.GetDeviceInfo().GetSerialNumber())
    print("full size  ", cam.WidthMax.GetValue(), "x", cam.HeightMax.GetValue())
    print("pixel fmt  ", cam.PixelFormat.GetValue())
    print("exposure   ", cam.ExposureTime.GetValue(), "us, range",
          cam.ExposureTime.GetMin(), "-", cam.ExposureTime.GetMax())
    print("gain       ", cam.Gain.GetValue(), "range", cam.Gain.GetMin(), "-", cam.Gain.GetMax())

    # 先按默认设置抓一帧，看看有没有光
    try:
        cam.AcquisitionFrameRateEnable.SetValue(True)
        cam.AcquisitionFrameRate.SetValue(20.0)
    except Exception as exc:
        print("framerate set failed:", exc)

    cam.StartGrabbing(pylon.GrabStrategy_LatestImageOnly)
    conv = pylon.ImageFormatConverter()
    conv.OutputPixelFormat = pylon.PixelType_Mono16
    n = 5
    stats = []
    last = None
    k = 0
    while k < n and cam.IsGrabbing():
        res = cam.RetrieveResult(5000, pylon.TimeoutHandling_ThrowException)
        if res.GrabSucceeded():
            img = conv.Convert(res).GetArray()
            last = img
            stats.append((float(img.mean()), int(img.min()), int(img.max())))
            k += 1
        res.Release()
    cam.StopGrabbing()
    cam.Close()

    for i, (m, lo, hi) in enumerate(stats):
        print(f"frame {i}: mean={m:8.1f}  min={lo:5d}  max={hi:5d}")
    if last is not None:
        np.save(r"D:\课题组\slm\probe_frame.npy", last)
        print("saved probe_frame.npy shape", last.shape, last.dtype)
    return 0

if __name__ == "__main__":
    sys.exit(main())
