# -*- coding: utf-8 -*-
"""在 SLM 上显示黑白十字（准直/对中用的十字线）。

默认：黑底 + 白十字（水平竖直各一条，贯穿全屏，中心有一个小实心方块）。
可选反转、以及"十字外黑内白 / 外白内黑"交替闪烁。

用法:
    python slm_cross.py                        # 黑底白十字，显示 60 s
    python slm_cross.py --hold 0               # 一直显示，Ctrl+C 停
    python slm_cross.py --invert               # 白底黑十字
    python slm_cross.py --thickness 8          # 加粗
    python slm_cross.py --blink 1 --hold 30    # 1 Hz 黑白十字交替
"""
import argparse
import os
import sys
import threading
import time

import numpy as np

from slm_driver import SLM


def make_cross(h, w, thickness=3, invert=False, center_block=True, arm_ratio=1.0):
    """返回 uint8 (h, w) 图像：十字 + 中心块。"""
    img = np.full((h, w), 0, np.uint8)
    t = max(1, int(thickness))
    cy, cx = h // 2, w // 2

    # 水平臂
    half = int(w * arm_ratio / 2)
    img[cy - t // 2: cy + t - t // 2, max(0, cx - half): min(w, cx + half)] = 255
    # 竖直臂
    halfv = int(h * arm_ratio / 2)
    img[max(0, cy - halfv): min(h, cy + halfv), cx - t // 2: cx + t - t // 2] = 255

    if center_block:
        s = max(3, t * 2)
        img[cy - s // 2: cy + s - s // 2, cx - s // 2: cx + s - s // 2] = 255

    if invert:
        img = 255 - img
    return img


def main():
    ap = argparse.ArgumentParser(description='SLM 黑白十字')
    ap.add_argument('--hold', type=float, default=60.0, help='秒数，0 = 一直显示')
    ap.add_argument('--monitor', type=int, default=1)
    ap.add_argument('--thickness', type=int, default=3, help='线宽（像素，默认 3）')
    ap.add_argument('--arm', type=float, default=1.0, help='臂长占屏幕比例 0.1~1.0')
    ap.add_argument('--invert', action='store_true', help='白底黑十字')
    ap.add_argument('--blink', type=float, default=0.0,
                    help='黑白十字交替频率 Hz（0 = 不闪）')
    ap.add_argument('--save', default='', help='另存为 png')
    args = ap.parse_args()

    slm = SLM(monitor=args.monitor)
    W, H = slm.getSize()

    normal = make_cross(H, W, args.thickness, invert=args.invert, arm_ratio=args.arm)
    inverted = make_cross(H, W, args.thickness, invert=not args.invert, arm_ratio=args.arm)

    if args.save:
        try:
            from PIL import Image
            Image.fromarray(normal).save(args.save)
            print(f'已保存 {args.save}')
        except ImportError:
            print('（未装 Pillow，跳过保存）')

    print(f'SLM {W}x{H}：{args.thickness}px 十字，'
          f'{"黑白交替 %g Hz" % args.blink if args.blink > 0 else ("白底黑十字" if args.invert else "黑底白十字")}，'
          f'{"一直显示" if args.hold <= 0 else f"{args.hold:g} s"}')

    stop = threading.Event()

    def drive():
        if args.blink <= 0:
            slm.update(normal)
            if args.hold > 0:
                stop.wait(args.hold)
        else:
            period = 1.0 / max(1e-3, args.blink)
            t0 = time.perf_counter()
            while not stop.is_set():
                t = time.perf_counter() - t0
                slm.update(normal if (t % period) < period / 2 else inverted)
                if args.hold > 0 and t >= args.hold:
                    break
                time.sleep(1.0 / 60.0)
        stop.set()
        slm.close()

    th = threading.Thread(target=drive, daemon=True)
    th.start()
    try:
        slm.run()
    except KeyboardInterrupt:
        pass
    stop.set()
    print('结束')
    sys.stdout.flush()
    os._exit(0)


if __name__ == '__main__':
    main()
