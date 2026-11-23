# -*- coding: utf-8 -*-
"""让 SLM 全屏黑白闪烁。

用途：
  * 肉眼确认 SLM 面板在工作（黑/白整屏切换，无窗口边框）；
  * 相机侧验证曝光同步（如果曝光不是 16.7 ms 整数倍，会拍到中间灰）。

用法:
    python slm_blink.py                 # 2 Hz，闪 60 s
    python slm_blink.py --hz 1 --hold 0 # 1 Hz，一直闪直到 Ctrl+C
    python slm_blink.py --hz 5 --hold 30
"""
import argparse
import os
import sys
import threading
import time

import numpy as np

from slm_driver import SLM


def main():
    ap = argparse.ArgumentParser(description='SLM 黑白闪烁')
    ap.add_argument('--hz', type=float, default=2.0, help='完整黑/白周期数每秒（默认 2）')
    ap.add_argument('--hold', type=float, default=60.0, help='秒数，0 = 一直闪')
    ap.add_argument('--monitor', type=int, default=1)
    ap.add_argument('--duty', type=float, default=0.5, help='白色占空比 0..1（默认 0.5）')
    args = ap.parse_args()

    slm = SLM(monitor=args.monitor)
    W, H = slm.getSize()
    white = np.full((H, W), 255, np.uint8)
    black = np.zeros((H, W), np.uint8)
    print(f'SLM {W}x{H}，{args.hz:g} Hz 黑白闪烁，占空比 {args.duty:g}，'
          f'{"一直闪" if args.hold <= 0 else f"{args.hold:g} s"}')
    print('（Ctrl+C 停止；SLM 面板上应看到整屏黑/白切换）')

    stop = threading.Event()
    period = 1.0 / max(1e-3, args.hz)

    def blink():
        t0 = time.perf_counter()
        n = 0
        try:
            while not stop.is_set():
                t = time.perf_counter() - t0
                phase = (t % period) / period
                slm.update(white if phase < args.duty else black)
                n += 1
                # 每个刷新周期只推一次，60 Hz 足够
                time.sleep(1.0 / 60.0)
                if args.hold > 0 and t >= args.hold:
                    break
        finally:
            slm.close()

    th = threading.Thread(target=blink, daemon=True)
    th.start()
    try:
        slm.run()
    except KeyboardInterrupt:
        pass
    stop.set()
    print('结束')
    sys.stdout.flush()
    os._exit(0)  # 跳过 wx teardown（会崩/挂）


if __name__ == '__main__':
    main()
