#!/usr/bin/env python3
"""Проверка временных пропусков в .xyz файле.
Считает количество интервалов > 0.15 с, показывает топ-20."""
import sys
from datetime import datetime

path = sys.argv[1]
prev = None
gaps = []
n = 0
first = None
last = None

# Сначала собираем все эпохи, потом сортируем по времени (важно для backward-pos)
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
        rows.append(dt)

rows.sort()
for i, dt in enumerate(rows):
    n += 1
    if i == 0:
        first = dt
    if i > 0:
        dt_gap = (dt - rows[i-1]).total_seconds()
        if dt_gap > 0.15:
            gaps.append((rows[i-1], dt, dt_gap))
    last = dt

total_span = (last - first).total_seconds()
expected = round(total_span / 0.1) + 1

print(f"Файл: {path}")
print(f"  эпох в файле:      {n}")
print(f"  первая:            {first}")
print(f"  последняя:         {last}")
print(f"  длительность:      {total_span:.2f} с")
print(f"  ожидалось (10 Гц): {expected}")
print(f"  пропущено эпох:    {expected - n} ({(expected - n) / expected * 100:.2f}%)")
print(f"  интервалов >0.15с: {len(gaps)}")
if gaps:
    gaps_sorted = sorted(gaps, key=lambda x: -x[2])[:20]
    print(f"  ТОП-20 наибольших пропусков:")
    for start, end, dur in gaps_sorted:
        print(f"    {start.strftime('%H:%M:%S.%f')[:-3]} → {end.strftime('%H:%M:%S.%f')[:-3]}  пропуск {dur:.2f} с ({int(dur * 10)} эпох)")
