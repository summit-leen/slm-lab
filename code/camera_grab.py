# -*- coding: utf-8 -*-
"""抓一帧看看相机是否正常工作，并保存图像。

用法:
    python camera_grab.py                 # 自动曝光，抓 5 帧
    python camera_grab.py --exp 20000     # 手动曝光 20 ms
    python camera_grab.py --out D:\\课题\slm\\captures\\shot
"""
import argparse
import os
import sys
import time

import numpy as np
from pypylon import pylon


def to_png(path_no_ext, arr):
    """用 PIL 或 wx 存 PNG，都没有就只留 .npy。"""
    try:
        from PIL import Image
        Image.fromarray(arr).save(path_no_ext + '.png')
        return path_no_ext + '.png'
    except Exception:
        pass
    try:
        import wx
        h, w = arr.shape
        rgb = np.repeat(arr[:, :, None], 3, axis=2)
        img = wx.Image(w, h, rgb.tobytes())
        img.SaveFile(path_no_ext + '.png', wx.BITMAP_TYPE_PNG)
        return path_no_ext + '.png'
    except Exception as e:
        print('PNG 保存失败:', type(e).__name__, e)
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--exp', type=float, default=0, help='曝光 us，0 = 自动')
    ap.add_argument('--gain', type=float, default=0.0, help='增益 dB')
    ap.add_argument('--frames', type=int, default=5, help='抓几帧统计')
    ap.add_argument('--out', default=r'D:\课题组\slm\captures\shot')
    ap.add_argument('--roi', type=int, default=0, help='>0 时取中心 ROI 的边长')
    args = ap.parse_args()

    tl = pylon.TlFactory.GetInstance()
    devs = tl.EnumerateDevices()
    if not devs:
        print('没有发现相机')
        return 1
    d = devs[0]
    print(f'设备: {d.GetModelName()} / SN {d.GetSerialNumber()}')

    cam = pylon.InstantCamera(tl.CreateDevice(d))
    cam.Open()
    try:
        print('  链路速度:', end=' ')
        try:
            print(cam.DeviceLinkSpeed.Value, 'Mbps')
        except Exception:
            print('<不可读>')

        cam.PixelFormat.Value = 'Mono8'
        cam.Width.Value = cam.WidthMax.Value
        cam.Height.Value = cam.HeightMax.Value
        if args.roi > 0:
            side = min(args.roi, cam.Width.Value, cam.Height.Value)
            cam.Width.Value = side
            cam.Height.Value = side
            cam.OffsetX.Value = (cam.WidthMax.Value - side) // 2
            cam.OffsetY.Value = (cam.HeightMax.Value - side) // 2

        if args.exp > 0:
            cam.ExposureAuto.Value = 'Off'
            cam.ExposureTime.Value = args.exp
            print(f'  手动曝光 {args.exp / 1000:.1f} ms')
        else:
            cam.ExposureAuto.Value = 'Continuous'
            print('  自动曝光')
        cam.GainAuto.Value = 'Off'
        cam.Gain.Value = args.gain

        print(f'  当前帧尺寸 {cam.Width.Value}x{cam.Height.Value}')
        cam.StartGrabbing(pylon.GrabStrategy_LatestImageOnly)
        frames = []
        t0 = time.time()
        while len(frames) < args.frames and cam.IsGrabbing():
            res = cam.RetrieveResult(2000, pylon.TimeoutHandling_ThrowException)
            if res.GrabSucceeded():
                frames.append(res.GetArray().copy())
                if len(frames) == 1:
                    exp = cam.ExposureTime.Value if args.exp > 0 else None
                    print(f'  实际曝光 {exp/1000:.2f} ms' if exp else '  实际曝光 <自动>')
            res.Release()
        dt = time.time() - t0
        cam.StopGrabbing()
    finally:
        cam.Close()

    if not frames:
        print('没抓到帧')
        return 1

    print(f'  抓了 {len(frames)} 帧，用时 {dt:.2f} s（{len(frames)/dt:.1f} fps）')
    img = frames[0]
    print(f'  第一帧 dtype={img.dtype} shape={img.shape}')
    print(f'  灰度 min={img.min()} max={img.max()} mean={img.mean():.1f} '
          f'std={img.std():.1f}')
    sat = (img == 255).mean() * 100
    print(f'  饱和像素 {sat:.2f}%')
    if len(frames) > 1:
        stack = np.stack([f.astype(np.float32) for f in frames])
        print(f'  {len(frames)} 帧时间噪声 std 均值 = {stack.std(axis=0).mean():.2f}')

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    np.save(args.out + '.npy', img)
    print('  已保存', args.out + '.npy')
    png = to_png(args.out, img)
    if png:
        print('  已保存', png)
    return 0


if __name__ == '__main__':
    sys.exit(main())
