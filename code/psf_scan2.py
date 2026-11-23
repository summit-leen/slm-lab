# -*- coding: utf-8 -*-
"""轴向 PSF 扫描（单进程版）：一个 SLM 窗口 + 一次相机打开，按 f 序列切换。

与 psf_scan.py 的区别：不反复 spawn slm_show 子进程（反复开关全屏窗口会让
DISPLAY2 偶尔抓不到新窗口，表现为"图案没上屏"），而是同一个窗口内换图案。

    python code/psf_scan2.py --fs 38 38.5 39 39.5 40 40.5 41 41.5 42 \
        --exposures 3000 10000 40000 --frames 8 --out captures/psf_ax
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import threading
import time

import numpy as np
from pypylon import pylon

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import random_lens_array as rla  # noqa: E402
import slm_driver  # noqa: E402

W, H = 1024, 768


def grab(cam, exp_us: float, n: int) -> tuple[np.ndarray, np.ndarray]:
    cam.ExposureTime.Value = float(exp_us)
    frames = []
    cam.StartGrabbing(pylon.GrabStrategy_LatestImageOnly)
    t0 = time.time()
    while len(frames) < n and time.time() - t0 < 20:
        r = cam.RetrieveResult(3000, pylon.TimeoutHandling_ThrowException)
        if r.GrabSucceeded():
            frames.append(r.GetArray().copy())
        r.Release()
    cam.StopGrabbing()
    st = np.stack(frames).astype(np.float32)
    return st.mean(axis=0), st[0].astype(np.uint8)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fs", type=float, nargs="+",
                    default=[38, 38.5, 39, 39.5, 40, 40.5, 41, 41.5, 42])
    ap.add_argument("--exposures", type=float, nargs="+", default=[3000, 10000, 40000])
    ap.add_argument("--frames", type=int, default=8)
    ap.add_argument("--n", type=int, default=80)
    ap.add_argument("--seed", type=int, default=20261123)
    ap.add_argument("--L", type=float, default=200.0, help="小孔到面板 mm")
    ap.add_argument("--r-max", type=float, default=36.0)
    ap.add_argument("--settle", type=float, default=0.5, help="换图后等待秒数")
    ap.add_argument("--out", default="captures/psf_ax")
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)

    gen = argparse.Namespace(
        n=args.n, f_min=min(args.fs), f_max=max(args.fs), r_min=9.0,
        r_max=args.r_max, alias_frac=0.95, size_skew=0.75, gap=4.0,
        margin=6.0, pitch=18.0, lam=620.0, gamma=400.0, sign=-1,
        tilt=(0.0, 0.0), overlap=False,
    )
    rng = np.random.default_rng(args.seed)
    base = rla.build_layout(W, H, gen, rng)
    geom = [(L.cx, L.cy, L.r) for L in base]
    print(f"冻结布局 {len(geom)} 枚，半径 {min(g[2] for g in geom):.1f}..{max(g[2] for g in geom):.1f} px",
          flush=True)

    tl = pylon.TlFactory.GetInstance()
    devs = tl.EnumerateDevices()
    if not devs:
        print("没有发现相机")
        return 1

    slm = slm_driver.SLM(monitor=1)
    cam = pylon.InstantCamera(tl.CreateDevice(devs[0]))
    cam.Open()
    cam.PixelFormat.Value = "Mono8"
    cam.Width.Value = cam.WidthMax.Value
    cam.Height.Value = cam.HeightMax.Value
    cam.ExposureAuto.Value = "Off"
    cam.GainAuto.Value = "Off"
    cam.Gain.Value = 0.0

    meta = {"L_mm": args.L, "pitch_um": gen.pitch, "lam_nm": gen.lam,
            "gamma_nm": gen.gamma, "seed": args.seed, "n_lenses": len(geom),
            "exposures_us": args.exposures, "frames": args.frames, "steps": []}
    done = threading.Event()

    def sequence():
        try:
            for f_mm in args.fs:
                lenses = [rla.Lens(cx, cy, r, f_mm * 1e-3, gen.pitch * 1e-6)
                          for cx, cy, r in geom]
                pat = rla.build_pattern(W, H, lenses, gen)
                z = f_mm * args.L / (args.L - f_mm)
                slm.update(pat)
                time.sleep(args.settle)
                print(f"f={f_mm:g} mm → z={z:.2f} mm", flush=True)
                step = {"f_mm": f_mm, "z_mm": round(z, 3), "files": []}
                for exp in args.exposures:
                    mean, first = grab(cam, exp, args.frames)
                    tag = f"f{f_mm:g}_exp{int(exp)}"
                    np.save(os.path.join(args.out, tag + "_mean.npy"), mean)
                    np.save(os.path.join(args.out, tag + "_first.npy"), first)
                    print(f"   {tag}: mean {mean.mean():.2f} max {mean.max():.0f} "
                          f"p99.9 {np.percentile(mean, 99.9):.1f}", flush=True)
                    step["files"].append(tag)
                meta["steps"].append(step)
        finally:
            with open(os.path.join(args.out, "meta.json"), "w", encoding="utf-8") as fh:
                json.dump(meta, fh, ensure_ascii=False, indent=2)
            cam.Close()
            slm.close()
            print("完成", flush=True)
            done.set()

    threading.Thread(target=sequence, daemon=True).start()
    try:
        slm.run()
    except KeyboardInterrupt:
        pass
    done.wait(5)
    os._exit(0)


if __name__ == "__main__":
    raise SystemExit(main())
