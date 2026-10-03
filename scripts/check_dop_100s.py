#!/usr/bin/env python3
"""Проверка ТЗ: DOP не более 10 в течение 100 секунд.
Ищет все непрерывные интервалы, где PDOP/HDOP/VDOP > порога, и проверяет,
есть ли хоть один длиной >= 100 секунд.
"""
import sys
from datetime import datetime

path = sys.argv[1]
threshold = float(sys.argv[2]) if len(sys.argv) > 2 else 10.0

# Для каждого DOP — список (start_dt, end_dt) непрерывных интервалов > threshold
dop_cols = {'PDOP': 6, 'HDOP': 7, 'VDOP': 8}
active = {k: None for k in dop_cols}   # (start_dt, last_dt)
longest = {k: 0.0 for k in dop_cols}   # сек
gaps = {k: [] for k in dop_cols}       # список (start, end, duration_s)

def close(k, dt):
    if active[k]:
        start, _ = active[k]
        dur = (dt - start).total_seconds()
        if dur > longest[k]:
            longest[k] = dur
        gaps[k].append((start, dt, dur))
        active[k] = None

# Собираем всё в список, сортируем по времени (backward-pos)
rows = []
with open(path) as f:
    for line in f:
        if line.startswith('/') or not line.strip():
            continue
        p = line.split()
        try:
            dt = datetime.strptime(f"{p[0]} {p[1]}", "%Y/%m/%d %H:%M:%S.%f")
        except (ValueError, IndexError):
            continue
        rows.append((dt, p))

rows.sort(key=lambda r: r[0])
if rows:
    prev_dt = None
    for dt, p in rows:
        for k, col in dop_cols.items():
            try:
                v = float(p[col - 1])
            except (ValueError, IndexError):
                continue
            if v > threshold:
                if active[k] is None:
                    active[k] = (dt, dt)
                else:
                    start, _ = active[k]
                    active[k] = (start, dt)
            else:
                if active[k]:
                    close(k, dt)
        prev_dt = dt

    # Закрыть незакрытые интервалы
    if prev_dt:
        for k in dop_cols:
            if active[k]:
                close(k, prev_dt)

print(f"Файл: {path}")
print(f"Порог DOP: {threshold}")
print(f"Критерий ТЗ: непрерывный интервал не более 100 сек")
print()
for k in dop_cols:
    g = gaps[k]
    print(f"--- {k} ---")
    print(f"  интервалов выше порога: {len(g)}")
    print(f"  самый длинный непрерывный: {longest[k]:.2f} сек")
    if g:
        g_sorted = sorted(g, key=lambda x: -x[2])[:5]
        print(f"  топ-5 по длительности:")
        for start, end, dur in g_sorted:
            print(f"    {start.strftime('%H:%M:%S.%f')[:-3]} → {end.strftime('%H:%M:%S.%f')[:-3]}  {dur:.2f} с")
    if longest[k] <= 100:
        print(f"  ✅ ПРОХОДИТ ТЗ (max {longest[k]:.2f} сек ≤ 100)")
    else:
        print(f"  ❌ НАРУШЕНИЕ ТЗ ({longest[k]:.2f} сек > 100)")
