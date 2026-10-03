#!/usr/bin/env python3
"""detect_anomaly.py — опциональный детектор аномальных Q1-эпох.
НЕ меняет result.pos. Только помечает подозрительные эпохи для ручного аудита.

Критерий: k = Δ / max(MAD_fwd, MAD_bwd, 0.05) > 50 AND MAD_max < 0.5.

Usage:
    detect_anomaly.py <result.pos> [<seg_dir_1> <seg_dir_2> ...] [--out report.txt]

Если <seg_dir_N> не указаны — скрипт сам ищет seg_* в директории result.pos.
"""
import os, sys, glob, math
from datetime import datetime

DIV_THR  = 50.0
MAD_THR  = 0.5
MAD_FLOOR = 0.05

def r100(t):
    return t.replace(microsecond=(t.microsecond // 100000) * 100000)

def load_pos(p):
    d = {}
    if not os.path.exists(p): return d
    with open(p) as f:
        for line in f:
            if line.startswith('%') or not line.strip(): continue
            x = line.split()
            if len(x) < 6: continue
            try:
                dt = datetime.strptime(f"{x[0]} {x[1]}", "%Y/%m/%d %H:%M:%S.%f")
            except: continue
            d[r100(dt)] = (float(x[4]), int(x[5]))
    return d

def median(arr):
    if not arr: return None
    s = sorted(arr); n = len(s)
    return s[n//2] if n % 2 else (s[n//2-1] + s[n//2]) / 2.0

def mad(arr):
    if len(arr) < 2: return 0.0
    m = median(arr)
    return 1.4826 * median([abs(x - m) for x in arr])

def main():
    if len(sys.argv) < 2:
        print(__doc__); sys.exit(1)
    pos_path = sys.argv[1]
    out_path = None
    seg_dirs = []
    i = 2
    while i < len(sys.argv):
        a = sys.argv[i]
        if a == "--out":
            i += 1
            if i < len(sys.argv): out_path = sys.argv[i]
        elif os.path.isdir(a):
            seg_dirs.append(a)
        i += 1

    if not seg_dirs:
        base = os.path.dirname(os.path.abspath(pos_path))
        seg_dirs = sorted(glob.glob(f"{base}/seg_*"))
        if not seg_dirs:
            ens = f"{base}/ensemble"
            if os.path.exists(f"{ens}/e15_forward.pos"):
                seg_dirs = [ens]

    if not seg_dirs:
        print(f"ERROR: не найдено seg_*/ensemble рядом с {pos_path}", file=sys.stderr)
        sys.exit(1)

    runs = {}
    for sd in seg_dirs:
        for f in sorted(glob.glob(f"{sd}/*.pos")):
            if "_events" in f: continue
            name = os.path.basename(f)[:-4]
            d = load_pos(f)
            if name not in runs: runs[name] = {}
            runs[name].update(d)

    res = load_pos(pos_path)
    run_names = sorted(runs.keys())
    fwd = [n for n in run_names if n.endswith("_forward")]
    bwd = [n for n in run_names if n.endswith("_backward")]

    if not fwd or not bwd:
        print(f"ERROR: нет forward/backward прогонов", file=sys.stderr)
        sys.exit(1)

    flagged = []  # (t, h_q1, med_fwd, med_bwd, delta, mad_fwd, mad_bwd, k)
    n_q1 = 0
    for t, x in res.items():
        if x[1] != 1: continue
        n_q1 += 1
        h_q1 = x[0]
        fwd_hs = []; bwd_hs = []
        for n in fwd:
            y = runs[n].get(t)
            if y is not None: fwd_hs.append(y[0])
        for n in bwd:
            y = runs[n].get(t)
            if y is not None: bwd_hs.append(y[0])
        if not fwd_hs or not bwd_hs: continue
        mf = median(fwd_hs); mb = median(bwd_hs)
        delta = abs(mf - mb)
        mad_fwd = mad(fwd_hs); mad_bwd = mad(bwd_hs)
        mad_max = max(mad_fwd, mad_bwd, MAD_FLOOR)
        k = delta / mad_max
        if k > DIV_THR and mad_max < MAD_THR:
            flagged.append((t, h_q1, mf, mb, delta, mad_fwd, mad_bwd, k))

    # Группируем в серии
    flagged.sort(key=lambda r: r[0])
    series = []
    if flagged:
        cur = [flagged[0]]
        for i in range(1, len(flagged)):
            dt = (flagged[i][0] - flagged[i-1][0]).total_seconds()
            if dt <= 1.0:
                cur.append(flagged[i])
            else:
                series.append(cur)
                cur = [flagged[i]]
        series.append(cur)

    # Отчёт
    lines = []
    def out(s=""):
        print(s)
        lines.append(s)

    out(f"=== detect_anomaly report ===")
    out(f"pos: {pos_path}")
    out(f"seg_dirs: {len(seg_dirs)}")
    out(f"runs: {len(run_names)} ({len(fwd)} fwd, {len(bwd)} bwd)")
    out(f"Q1 total: {n_q1}")
    out(f"flagged: {len(flagged)} ({100*len(flagged)/n_q1:.3f} %)" if n_q1 else "flagged: 0")
    out(f"series: {len(series)}")
    if series:
        runs_len = [len(s) for s in series]
        runs_sec = [(s[-1][0]-s[0][0]).total_seconds() for s in series]
        out(f"  max series: {max(runs_len)} эпох / {max(runs_sec):.1f} сек")
        out()
        out(f"Топ-10 серий по длительности:")
        idx = sorted(range(len(series)), key=lambda i: -runs_sec[i])[:10]
        for i in idx:
            s = series[i]
            dur = runs_sec[i]
            out(f"  {s[0][0]} → {s[-1][0]}  n={len(s):>5}  dur={dur:>7.1f}с  "
                f"med_k={median([r[7] for r in s]):.1f}  "
                f"med_Δ={median([r[4] for r in s]):.2f}м")

    if out_path:
        with open(out_path, "w") as f:
            f.write("\n".join(lines) + "\n")
        print(f"\nreport -> {out_path}")

if __name__ == "__main__":
    main()
