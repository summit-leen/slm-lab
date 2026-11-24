# -*- coding: utf-8 -*-
"""连拍 N 帧（间隔 dt 秒），用来判断"物体是否在光路里"。

    python code/wave_test.py --n 12 --dt 1.5 --exp 400 --out captures/wave

原理：拍摄期间请人把物体移开/放回。若物体在光路里，帧间差会在
物体区域出现明显变化；若只是均匀背景，帧间差只有噪声水平。
"""
from __future__ import annotations

import argparse
import time

import numpy as np
from pypylon import pylon


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=12)
    ap.add_argument("--dt", type=float, default=1.5)
    ap.add_argument("--exp", type=float, default=400.0)
    ap.add_argument("--out", default="captures/wave")
    args = ap.parse_args()

    cam = pylon.InstantCamera(pylon.TlFactory.GetInstance().CreateFirstDevice())
    cam.Open()
    cam.ExposureTime.SetValue(args.exp)
    cam.StartGrabbing(pylon.GrabStrategy_LatestImageOnly)

    frames = []
    t0 = time.time()
    for k in range(args.n):
        g = cam.RetrieveResult(5000, pylon.TimeoutHandling_ThrowException)
        if g.IsValid():
            frames.append(g.GetArray().copy())
        g.Release()
        print(f"  frame {k+1}/{args.n}  t={time.time()-t0:.1f}s", flush=True)
        time.sleep(args.dt)
    cam.StopGrabbing()
    cam.Close()

    st = np.stack(frames).astype(np.float32)
    np.save(f"{args.out}_stack.npy", st)
    sd = st.std(axis=0)
    np.save(f"{args.out}_std.npy", sd)
    print(f"帧间 std：全场均值 {sd.mean():.2f}  最大 {sd.max():.2f}  "
          f"p99.9 {np.percentile(sd,99.9):.2f}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
