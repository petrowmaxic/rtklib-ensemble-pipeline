#!/usr/bin/env python3
"""Сравнение RTKLIB .pos с GrafNav .xyz по GPST. Показывает статистику отдельно
для всех эпох и отдельно только для Q=1 (fix)."""
import sys, math
from datetime import datetime
from collections import defaultdict


def parse_pos(path):
    out = {}
    with open(path) as f:
        for line in f:
            if line.startswith('%') or not line.strip():
                continue
            p = line.split()
            if len(p) < 6:
                continue
            try:
                dt = datetime.strptime(f"{p[0]} {p[1]}", "%Y/%m/%d %H:%M:%S.%f")
                lat, lon, h, q = float(p[2]), float(p[3]), float(p[4]), int(p[5])
            except (ValueError, IndexError):
                continue
            out[dt] = (lat, lon, h, q)
    return out


def parse_xyz_grafnav(path):
    out = {}
    with open(path) as f:
        for line in f:
            if line.startswith('/') or not line.strip():
                continue
            p = line.split()
            if len(p) < 5:
                continue
            try:
                dt = datetime.strptime(f"{p[0]} {p[1]}", "%Y/%m/%d %H:%M:%S.%f")
                lon, lat, h = float(p[2]), float(p[3]), float(p[4])
            except (ValueError, IndexError):
                continue
            out[dt] = (lat, lon, h)
    return out


def stats(a):
    n = len(a)
    if n == 0:
        return None
    a_s = sorted(a)
    mean = sum(a) / n
    rms = (sum(x * x for x in a) / n) ** 0.5
    median = a_s[n // 2] if n % 2 else (a_s[n // 2 - 1] + a_s[n // 2]) / 2
    return {'n': n, 'mean': mean, 'median': median, 'rms': rms,
            'min': a_s[0], 'max': a_s[-1],
            'p95': a_s[int(0.95 * n)],
            'max_abs': max(abs(x) for x in a)}


BINS = [(0, 0.01), (0.01, 0.05), (0.05, 0.10), (0.10, 0.30),
        (0.30, 1.0), (1.0, 5.0), (5.0, float('inf'))]


def print_block(label, arr):
    s = stats(arr)
    if not s:
        print(f"  {label}: нет данных")
        return
    print(f"  {label}: n={s['n']}  mean={s['mean']:+.4f}  median={s['median']:+.4f}  "
          f"RMS={s['rms']:.4f}  max_abs={s['max_abs']:.4f}  p95={s['p95']:+.4f}")
    for lo, hi in BINS:
        cnt = sum(1 for x in arr if lo <= abs(x) < hi)
        hi_s = f"{hi:5.2f}" if hi != float('inf') else "   ∞ "
        print(f"    {lo:5.2f}–{hi_s} м: {cnt:6d} ({100*cnt/len(arr):5.1f}%)")


def compare(rtk_path, ref_path, label, dump_csv=None):
    rtk = parse_pos(rtk_path)
    ref = parse_xyz_grafnav(ref_path)
    common = sorted(set(rtk) & set(ref))
    print(f"=== {label} ===")
    print(f"  rtk epochs: {len(rtk)}  ref epochs: {len(ref)}  common: {len(common)}")
    if not common:
        print("  НЕТ ОБЩИХ ЭПОХ"); return

    R = 6371000.0
    rows = []
    for t in common:
        lat_r, lon_r, h_r, q = rtk[t]
        lat_g, lon_g, h_g = ref[t]
        d_h = h_r - h_g
        d_lat = (lat_r - lat_g) * math.pi / 180 * R
        d_lon = (lon_r - lon_g) * math.pi / 180 * R * math.cos(math.radians(lat_r))
        rows.append((t, d_h, d_lat, d_lon, q))

    print("  --- ВСЕ ЭПОХИ ---")
    print_block("dH (м)  ", [r[1] for r in rows])
    print_block("dLat (м)", [r[2] for r in rows])
    print_block("dLon (м)", [r[3] for r in rows])

    fix_rows = [r for r in rows if r[4] == 1]
    if fix_rows:
        print(f"  --- ТОЛЬКО Q=1 (fix), n={len(fix_rows)} ---")
        print_block("dH (м)  ", [r[1] for r in fix_rows])
        print_block("dLat (м)", [r[2] for r in fix_rows])
        print_block("dLon (м)", [r[3] for r in fix_rows])

    print(f"  |dH| медиана по 10-мин интервалам (все эпохи):")
    buckets = defaultdict(list)
    for t, d_h, _, _, _ in rows:
        key = t.replace(minute=(t.minute // 10) * 10, second=0, microsecond=0)
        buckets[key].append(abs(d_h))
    for k in sorted(buckets):
        arr = buckets[k]
        arr_s = sorted(arr)
        med = arr_s[len(arr_s)//2]
        mx = arr_s[-1]
        print(f"    {k.strftime('%H:%M')}  n={len(arr):5d}  median={med*100:7.2f} см  max={mx*100:8.2f} см")

    if dump_csv:
        with open(dump_csv, 'w') as f:
            f.write("GPST,dH_m,dLat_m,dLon_m,Q_rtk\n")
            for t, d_h, d_lat, d_lon, q in rows:
                f.write(f"{t.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]},{d_h:+.4f},{d_lat:+.4f},{d_lon:+.4f},{q}\n")
        print(f"  CSV: {dump_csv}")


if __name__ == '__main__':
    if len(sys.argv) < 4:
        print("usage: compare_q1.py <rtklib.pos> <grafnav.xyz> <label> [dump.csv]")
        sys.exit(1)
    label = sys.argv[3]
    dump = sys.argv[4] if len(sys.argv) > 4 else None
    compare(sys.argv[1], sys.argv[2], label, dump)
