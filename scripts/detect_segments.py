#!/usr/bin/env python3
"""detect_segments.py <rover.26O> [gap_sec=300] [min_seg_sec=300]
Парсит RINEX obs, находит gaps, выводит сегменты в stdout:
  YYYY/MM/DD HH:MM:SS|YYYY/MM/DD HH:MM:SS
по одной на строку.
"""
import sys, re
from datetime import datetime

if len(sys.argv) < 2:
    print("usage: detect_segments.py <rover.26O> [gap_sec] [min_seg_sec]",
          file=sys.stderr)
    sys.exit(1)

path = sys.argv[1]
GAP = float(sys.argv[2]) if len(sys.argv) > 2 else 300.0
MIN_SEG = float(sys.argv[3]) if len(sys.argv) > 3 else 300.0

EPOCH3 = re.compile(
    r"^>\s*(\d{4})\s+(\d{1,2})\s+(\d{1,2})\s+"
    r"(\d{1,2})\s+(\d{1,2})\s+(\d{1,2}(?:\.\d+)?)")

times = []
with open(path, errors="ignore") as f:
    for line in f:
        m = EPOCH3.match(line)
        if not m:
            continue
        y, mo, d, hh, mm, ss = m.groups()
        sec = float(ss)
        dt = datetime(int(y), int(mo), int(d), int(hh), int(mm),
                      int(sec), int(round((sec - int(sec)) * 1e6)))
        times.append(dt)

if not times:
    print("ERROR: не найдено ни одной epoch в файле", file=sys.stderr)
    sys.exit(2)

times.sort()
segs = []
start = times[0]
for i in range(1, len(times)):
    if (times[i] - times[i-1]).total_seconds() > GAP:
        segs.append((start, times[i-1]))
        start = times[i]
segs.append((start, times[-1]))

out = []
for s, e in segs:
    if (e - s).total_seconds() >= MIN_SEG:
        out.append(f"{s.strftime('%Y/%m/%d %H:%M:%S')}|"
                   f"{e.strftime('%Y/%m/%d %H:%M:%S')}")

for line in out:
    print(line)

print(f"# total_epochs={len(times)} segments={len(out)}",
      file=sys.stderr)
