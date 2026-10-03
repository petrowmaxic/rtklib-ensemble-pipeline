#!/usr/bin/env python3
"""Анализ .pos: где ровер стоит, где летит.
Ищет стационарный период (v < v_thr длительностью >= min_dur).
usage: detect_warmup.py <file.pos> [v_thr_mps] [min_dur_sec]
"""
import sys, math
from datetime import datetime

def parse_pos(path):
    rows = []
    with open(path) as f:
        for line in f:
            if line.startswith('%') or not line.strip():
                continue
            p = line.split()
            if len(p) < 6:
                continue
            try:
                dt = datetime.strptime(f"{p[0]} {p[1]}", "%Y/%m/%d %H:%M:%S.%f")
                rows.append((dt, float(p[2]), float(p[3]), float(p[4]), int(p[5])))
            except (ValueError, IndexError):
                continue
    return rows

def hav(lat1, lon1, lat2, lon2):
    R = 6371000
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat/2)**2
         + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2))
         * math.sin(dlon/2)**2)
    return 2 * R * math.asin(math.sqrt(a))

def print_snapshot(rows, every_sec=300):
    """Печать состояния каждые N секунд — картину видно глазами."""
    print("Снимок (каждые {} сек):".format(every_sec))
    print(f"  {'время':<12}  {'lat':<13}  {'lon':<14}  {'h':<9}  Q  ns  v_гор(м/с)")
    t0 = rows[0][0]
    last_print = None
    for i in range(1, len(rows)):
        dt = (rows[i][0] - t0).total_seconds()
        if last_print is None or dt - last_print >= every_sec:
            cur = rows[i]
            dt_prev = (cur[0] - rows[i-1][0]).total_seconds()
            if dt_prev <= 0 or dt_prev > 1.0:
                v = -1
            else:
                v = hav(rows[i-1][1], rows[i-1][2], cur[1], cur[2]) / dt_prev
            tstr = cur[0].strftime('%H:%M:%S')
            print(f"  {tstr:<12}  {cur[1]:.9f}  {cur[2]:.9f}  {cur[3]:>8.3f}  {cur[4]}  "
                  f"{'-':>3}  {v:>6.2f}")
            last_print = dt

def find_static(rows, v_thr, min_dur_sec, q_required=1):
    """Возвращает (start_idx, end_idx, duration) длиннейшего статичного участка."""
    if len(rows) < 2:
        return None
    slow = [False] * len(rows)
    for i in range(1, len(rows)):
        dt = (rows[i][0] - rows[i-1][0]).total_seconds()
        if dt <= 0 or dt > 1.0:
            continue
        v = hav(rows[i-1][1], rows[i-1][2], rows[i][1], rows[i][2]) / dt
        if q_required and rows[i][4] != q_required:
            continue
        slow[i] = v < v_thr
    best_s = best_l = 0
    cur_s = cur_l = 0
    for i in range(len(slow)):
        if slow[i]:
            if cur_l == 0:
                cur_s = i
            cur_l += 1
            if cur_l > best_l:
                best_l = cur_l
                best_s = cur_s
        else:
            cur_l = 0
    if best_l == 0:
        return None
    dur = (rows[best_s + best_l - 1][0] - rows[best_s][0]).total_seconds()
    if dur < min_dur_sec:
        return None
    return (best_s, best_s + best_l - 1, dur)

def main():
    if len(sys.argv) < 2:
        print("usage: detect_warmup.py <file.pos> [v_thr=0.5] [min_dur=300]")
        sys.exit(1)
    path = sys.argv[1]
    v_thr = float(sys.argv[2]) if len(sys.argv) > 2 else 0.5
    min_dur = int(sys.argv[3]) if len(sys.argv) > 3 else 300

    rows = parse_pos(path)
    print(f"Файл: {path}")
    print(f"Всего эпох: {len(rows)}")
    if not rows:
        return
    print(f"Первая:    {rows[0][0]}")
    print(f"Последняя: {rows[-1][0]}")
    print()

    print_snapshot(rows, every_sec=300)
    print()

    res = find_static(rows, v_thr, min_dur)
    if res is None:
        print(f"Статичный период >= {min_dur} сек при v < {v_thr} м/с: НЕ НАЙДЕН")
        return

    s, e, dur = res
    n = e - s + 1
    lat = sum(rows[i][1] for i in range(s, e+1)) / n
    lon = sum(rows[i][2] for i in range(s, e+1)) / n
    h   = sum(rows[i][3] for i in range(s, e+1)) / n

    lat_range = (max(rows[i][1] for i in range(s, e+1))
                 - min(rows[i][1] for i in range(s, e+1))) * 111000
    lon_range = (max(rows[i][2] for i in range(s, e+1))
                 - min(rows[i][2] for i in range(s, e+1))) * 111000 * 0.5
    h_range = (max(rows[i][3] for i in range(s, e+1))
               - min(rows[i][3] for i in range(s, e+1)))

    print(f"НАЙДЕН статичный период:")
    print(f"  {rows[s][0]} → {rows[e][0]}")
    print(f"  длительность: {dur:.0f} с ({dur/60:.1f} мин), эпох: {n}")
    print(f"  центр:  lat={lat:.9f}  lon={lon:.9f}  h={h:.4f}")
    print(f"  разброс: lat={lat_range:.2f} м  lon={lon_range:.2f} м  h={h_range:.3f} м")
    print()
    print(f"ANCHOR: {lat:.9f} {lon:.9f} {h:.4f}")

if __name__ == '__main__':
    main()
