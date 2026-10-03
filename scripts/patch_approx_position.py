#!/usr/bin/env python3
"""Заменяет координаты в строке APPROX POSITION XYZ RINEX-файла.
usage: patch_approx_position.py <rinex.26O> <x> <y> <z>
"""
import sys

if len(sys.argv) != 5:
    print("usage: patch_approx_position.py <rinex.26O> <x> <y> <z>", file=sys.stderr)
    sys.exit(1)

path = sys.argv[1]
x, y, z = float(sys.argv[2]), float(sys.argv[3]), float(sys.argv[4])

with open(path) as f:
    lines = f.readlines()

found = False
for i, line in enumerate(lines):
    if 'APPROX POSITION XYZ' in line:
        lines[i] = f" {x:14.4f} {y:14.4f} {z:14.4f}                  APPROX POSITION XYZ\n"
        found = True
        break

if not found:
    print(f"WARN: строка APPROX POSITION XYZ не найдена в {path}", file=sys.stderr)
    sys.exit(1)

with open(path, 'w') as f:
    f.writelines(lines)
print(f"OK: {path} patched: {x} {y} {z}")
