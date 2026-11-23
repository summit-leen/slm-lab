# -*- coding: utf-8 -*-
"""Paced frame-rate probe for slm_driver: send N frames at a target rate."""
import sys
import threading
import time

import numpy as np

import slm_driver

N = int(sys.argv[1]) if len(sys.argv) > 1 else 180
HZ = float(sys.argv[2]) if len(sys.argv) > 2 else 60.0

slm = slm_driver.SLM(monitor=1)
W, H = slm.getSize()

paint_ms = []
orig_apply = slm.frame.apply


def timed_apply(w, h, buf):
    t0 = time.perf_counter()
    orig_apply(w, h, buf)
    paint_ms.append((time.perf_counter() - t0) * 1000)


slm.frame.apply = timed_apply


def worker():
    y, x = np.mgrid[0:H, 0:W]
    base = slm.paint_count
    t0 = time.perf_counter()
    n = 0
    period = 1.0 / HZ
    try:
        for i in range(N):
            img = ((((x // 8) + i) % 2) * 255).astype(np.uint8)
            slm.update(img)
            n += 1
            target = t0 + n * period
            dt = target - time.perf_counter()
            if dt > 0:
                time.sleep(dt)
        time.sleep(0.5)
        el = time.perf_counter() - t0
        painted = slm.paint_count - base
        print(f'sent {n} frames in {el:.2f}s ({n / el:.1f} fps), painted {painted} '
              f'({painted / el:.1f} fps)')
        if paint_ms:
            print(f'apply(): mean {np.mean(paint_ms):.2f} ms, max {np.max(paint_ms):.2f} ms, '
                  f'n={len(paint_ms)}')
    finally:
        slm.close()


threading.Thread(target=worker, daemon=True).start()
slm.run()
print('main loop exited')
