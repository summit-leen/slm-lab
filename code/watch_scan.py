# -*- coding: utf-8 -*-
"""从 align_watch 的日志里找出读数偏离基线的时间段。"""
import re
import sys

path = sys.argv[1] if len(sys.argv) > 1 else r"D:\课题组\slm\watch.log"
rows = []
with open(path, "rb") as f:
    for line in f.read().decode("gbk", "replace").splitlines():
        m = re.search(r"t=\s*([\d.]+)\s+mean=\s*([\d.]+)", line)
        if m:
            rows.append((float(m.group(1)), float(m.group(2))))

if not rows:
    print("没有解析到数据")
    raise SystemExit(1)

vals = [v for _, v in rows]
base = sorted(vals)[len(vals) // 2]
print(f"样本 {len(rows)} 条, 基线(中位) {base:.1f}")
low = [r for r in rows if r[1] < 0.5 * base]
print(f"低于基线一半的样本: {len(low)} 条")
runs = []
for t, v in low:
    if runs and t - runs[-1][1] < 1.5:
        runs[-1][1] = t
        runs[-1][2] = min(runs[-1][2], v)
    else:
        runs.append([t, t, v])
for a, b, v in runs:
    print(f"  t={a:6.1f} .. {b:6.1f} s   最低 {v:.1f}")
