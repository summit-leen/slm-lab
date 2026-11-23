# -*- coding: utf-8 -*-
"""让 SLM 当一枚菲涅尔（衍射）透镜用：生成二次相位图并显示到 SLM 屏。

物理约定
--------
薄透镜的相位是  phi(r) = -pi * r^2 / (lambda * f)，r 为到光轴的距离。
相位图只有 exp(i*phi) 有意义，所以可以按 2*pi 取模（这就是"菲涅尔"）。

但这块面板的相位行程不够一个整周期：
    phi_max = 2*pi * Gamma / lambda        (Gamma = 液晶延迟, 标称 400 nm)
620 nm 时 phi_max = 1.29*pi，即 alpha = Gamma/lambda = 0.645 个周期。
于是把"取模后的 0..2pi"线性压到"面板能给的 0..phi_max"，
等价于给相位图画 8 bit 时直接用 gray = phi_mod/(2*pi)*255（alpha 自动抵消）。

代价（这是本方案的核心限制，必须先知道）：
  * 焦点效率 eta ≈ sinc^2(1 - alpha)，620 nm 时约 65%；
  * 其余光里最大的一坨是零级直穿，份额 ≈ sinc^2(alpha) ≈ 20%，
    在相机上表现为焦点旁边一个不动的亮斑（换 f 时它不跟着动）；
  * 无起偏器时另有一半（非调制偏振分量）光完全不参与，形成均匀背景。

设计边界
--------
单像素相位差不能超过 pi（否则欠采样，图案混叠）：
    d(phi)/dr * p <= pi  ->  r <= lambda*f/(2p)
取满口径 r = min(W,H)*p/2 时需要
    f >= 2*p*r/lambda
18 µm / 620 nm 时，全口径需要 f >= ~530 mm；f 更短则只有中心一小圈有效，
等价于缩小了口径。这正是有效衍射角上限 lambda/(2p) ≈ 1° 的另一种说法。

用法
----
    python slm_lens.py                       # 默认 f=600 mm，显示 20 s
    python slm_lens.py --f 500 --hold 30
    python slm_lens.py --f 800 --save lens800.npy
    python slm_lens.py --f 600 --diag         # 只算不显示
    python slm_lens.py --f 600 --sign +1      # 会聚/发散互换
"""
from __future__ import annotations

import argparse
import math
import sys

import numpy as np

DEFAULT_PITCH_UM = 18.0     # 0.9" 版标称像素间距（二手来源）
DEFAULT_LAM_NM = 620.0      # 大恒 GCI-060401 红光 LED
DEFAULT_GAMMA_NM = 400.0    # 液晶延迟标称值
SENSOR_W_MM = 7.72          # Basler daA3840 短边（3860x2178 @2.0 µm）


def _sinc(x: float) -> float:
    if abs(x) < 1e-12:
        return 1.0
    return math.sin(math.pi * x) / (math.pi * x)


def build_lens(width: int, height: int, pitch_um: float, lam_nm: float,
               f_mm: float, gamma_nm: float = DEFAULT_GAMMA_NM,
               sign: int = -1, center=None, tilt=(0.0, 0.0),
               apodize: bool = True) -> np.ndarray:
    """返回 uint8 (H, W) 的透镜相位图。sign=-1 会聚，+1 发散。

    tilt = (qx, qy) 单位"周期/像素"，给整幅图叠一个线性相位（棱镜）。
    偏折角 theta = q*lambda/p，像在距离 s 处的横移 Delta = q*lambda*s/p。
    用途：把聚焦的像从零级直穿光里挪开（离轴照明），否则 92% 未调制光
    形成的亮背景会把像淹掉。
    """
    p = pitch_um * 1e-6
    lam = lam_nm * 1e-9
    f = f_mm * 1e-3
    if center is None:
        cx, cy = (width - 1) / 2.0, (height - 1) / 2.0
    else:
        cx, cy = center

    yy, xx = np.mgrid[0:height, 0:width].astype(np.float64)
    xm = (xx - cx) * p
    ym = (yy - cy) * p
    r2 = xm * xm + ym * ym

    phi = sign * math.pi * r2 / (lam * f)
    if tilt is not None:
        qx, qy = float(tilt[0]), float(tilt[1])
        if qx or qy:
            phi = phi + 2.0 * math.pi * (qx * (xx - cx) + qy * (yy - cy))
    phi_mod = np.mod(phi, 2.0 * math.pi)
    if apodize:
        # 口径截断：超过混叠极限的环带画出来只会散射杂光，直接设成 0 相位
        r_eff = min(min(width, height) * p / 2.0, lam * f / (2.0 * p))
        phi_mod = np.where(r2 <= r_eff * r_eff, phi_mod, 0.0)
    gray = np.rint(phi_mod / (2.0 * math.pi) * 255.0).clip(0, 255).astype(np.uint8)
    return gray


def describe(width, height, pitch_um, lam_nm, f_mm, gamma_nm,
             tilt=(0.0, 0.0), s_mm=None) -> str:
    p = pitch_um * 1e-6
    lam = lam_nm * 1e-9
    f = f_mm * 1e-3
    D_full = min(width, height) * p              # 短边为口径
    r_full = D_full / 2.0
    alpha = min(1.0, gamma_nm / lam_nm)

    f_min_full = 2.0 * p * r_full / lam          # 全口径不混叠所需最短焦距
    f_used = max(f, f_min_full)
    D_eff = min(D_full, 2.0 * lam * f / (2.0 * p))   # 实际有效口径
    r_eff = D_eff / 2.0
    zones = r_eff ** 2 / (2.0 * lam * f)
    step_edge = r_eff * p / (lam * f)            # 边缘每像素的周期数
    eta = _sinc(1.0 - alpha) ** 2
    eta0 = _sinc(alpha) ** 2
    airy = 1.22 * lam * f / D_eff if D_eff > 0 else float("inf")

    lines = [
        f"面板        {width}x{height}, 像素间距 {pitch_um:g} um, 全口径 {D_full*1e3:.1f} mm",
        f"波长/延迟   {lam_nm:g} nm, 行程 {gamma_nm:g} nm -> alpha = {alpha:.3f} 周期 ({alpha*2:.2f}pi rad)",
        f"目标焦距    {f_mm:g} mm",
        "",
        f"有效口径    {D_eff*1e3:.1f} mm  (r = {r_eff*1e3:.2f} mm), f/# = {f_eff_ratio(f, D_eff):.1f}",
        f"菲涅尔环数  {zones:.0f} 个周期",
        f"边缘采样    {step_edge:.3f} 周期/像素  (必须 < 0.5，>0.5 即混叠)",
        f"全口径最短  f >= {f_min_full*1e3:.0f} mm" if f < f_min_full else
        f"全口径可用  f = {f_mm:g} mm 已满足 (要求 >= {f_min_full*1e3:.0f} mm)",
        "",
        f"焦点效率    {eta*100:.0f}%   (sinc^2(1-alpha))",
        f"零级直穿    {eta0*100:.0f}%   (相机上是不随 f 移动的亮斑)",
        f"艾里半径    {airy*1e6:.1f} um  (直径约 {2*airy*1e6:.0f} um)",
    ]
    qx, qy = float(tilt[0]), float(tilt[1])
    if qx or qy:
        theta = math.hypot(qx, qy) * lam / p
        lines += ["",
                  f"离轴倾斜    q = ({qx:g}, {qy:g}) 周期/像素 -> 偏折 {theta*1e3:.1f} mrad"]
        if s_mm:
            s = s_mm * 1e-3
            lines.append(f"像面横移    s = {s_mm:g} mm: dx = {qx*lam*s/p*1e3:.2f} mm, "
                         f"dy = {qy*lam*s/p*1e3:.2f} mm")
    if s_mm:
        s = s_mm * 1e-3
        if s > f:
            d = 1.0 / (1.0 / f - 1.0 / s)
            m = s / d
            lines += ["",
                      f"成像条件    s = {s_mm:g} mm -> 物距 d = {d*1e3:.0f} mm "
                      f"(1/f = 1/d + 1/s)",
                      f"放大率      m = s/d = {m:.2f}, 物方视场 = {SENSOR_W_MM/m:.1f} mm "
                      f"(靶面 {SENSOR_W_MM:g} mm)"]
        elif s < f:
            lines.append(f"注意        s = {s_mm:g} mm < f, 无法成实像")
    return "\n".join(lines)


def f_eff_ratio(f_m: float, D: float) -> float:
    return f_m / D if D > 0 else float("inf")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="SLM 菲涅尔透镜图案")
    ap.add_argument("--f", type=float, default=600.0, help="焦距 mm (默认 600)")
    ap.add_argument("--pitch", type=float, default=DEFAULT_PITCH_UM, help="像素间距 um")
    ap.add_argument("--lam", type=float, default=DEFAULT_LAM_NM, help="波长 nm")
    ap.add_argument("--gamma", type=float, default=DEFAULT_GAMMA_NM, help="液晶延迟 nm")
    ap.add_argument("--sign", type=int, default=-1, choices=(-1, 1), help="-1 会聚 +1 发散")
    ap.add_argument("--monitor", type=int, default=1)
    ap.add_argument("--hold", type=float, default=20.0, help="显示秒数 (默认 20)")
    ap.add_argument("--save", default=None, help="另存为 .npy")
    ap.add_argument("--diag", action="store_true", help="只打印设计诊断，不显示")
    ap.add_argument("--full", action="store_true",
                    help="透镜相位铺满整幅屏：不截断混叠区，外层环照样画出来")
    ap.add_argument("--tilt", type=float, default=0.0,
                    help="离轴倾斜 qx，单位 周期/像素 (0.1 -> s=800mm 时横移 2.8 mm)")
    ap.add_argument("--tilt-y", type=float, default=0.0, help="离轴倾斜 qy 周期/像素")
    ap.add_argument("--s", type=float, default=None, help="SLM 到传感器的距离 mm（算横移/成像条件）")
    args = ap.parse_args(argv)

    from slm_driver import SLM

    probe = SLM(monitor=args.monitor, verbose=False)
    W, H = probe.getSize()
    tilt = (args.tilt, args.tilt_y)
    img = build_lens(W, H, args.pitch, args.lam, args.f, args.gamma, args.sign,
                     tilt=tilt, apodize=not args.full)

    print(describe(W, H, args.pitch, args.lam, args.f, args.gamma, tilt, args.s))
    print(f"\n图案: {W}x{H} uint8, 灰度范围 {img.min()}..{img.max()}, "
          f"均值 {img.mean():.1f}")
    if args.save:
        np.save(args.save, img)
        print(f"已保存 {args.save}")

    if args.diag:
        probe.close()
        return 0

    print(f"\n显示 {args.hold:g} s ... (Ctrl+C 或关窗口结束)")
    probe.update(img)
    probe.run(hold=args.hold)
    print("结束")
    sys.stdout.flush()
    # wx teardown 会以 0xC0000409 退出甚至挂住，直接硬退出
    import os
    os._exit(0)


if __name__ == "__main__":
    raise SystemExit(main())
