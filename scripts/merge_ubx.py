#!/usr/bin/env python3
"""Слияние нескольких UBX в один по хронологии.
Порядок определяется по TIME OF FIRST OBS из RINEX, полученного convbin.
usage: merge_ubx.py <output.ubx> <input1.ubx> [<input2.ubx> ...]
"""
import sys
import subprocess
import tempfile
import os
from datetime import datetime
from pathlib import Path

CONVBIN = os.path.expanduser("~/gnss_experiment/bin/convbin_EX")


def get_times(ubx_path, tmpdir):
    """Возвращает (first_dt, last_dt, size_bytes)."""
    base = Path(ubx_path).stem
    obs = os.path.join(tmpdir, base + ".26O")
    nav = os.path.join(tmpdir, base + ".26N")
    r = subprocess.run(
        [CONVBIN, "-r", "ubx", "-o", obs, "-n", nav, ubx_path],
        capture_output=True, text=True
    )
    if r.returncode != 0:
        raise RuntimeError(f"convbin failed on {ubx_path}: {r.stderr}")
    first_s = last_s = None
    with open(obs) as f:
        for line in f:
            if "TIME OF FIRST OBS" in line:
                first_s = line[:43].strip()
            if "TIME OF LAST OBS" in line:
                last_s = line[:43].strip()
            if "END OF HEADER" in line:
                break
    if not first_s or not last_s:
        raise RuntimeError(f"не найдены TIME OF OBS в {obs}")

    def parse(s):
        # '2026 9 20 21 11 1.0000000'
        p = s.split()
        return datetime(
            int(p[0]), int(p[1]), int(p[2]),
            int(p[3]), int(p[4]), int(float(p[5]))
        )

    return parse(first_s), parse(last_s), os.path.getsize(ubx_path)


def main():
    if len(sys.argv) < 3:
        print("usage: merge_ubx.py <output.ubx> <input1.ubx> [<input2.ubx> ...]")
        sys.exit(1)
    output = sys.argv[1]
    inputs = sys.argv[2:]

    # Проверка входных файлов
    for p in inputs:
        if not os.path.isfile(p):
            print(f"ERROR: не найден {p}")
            sys.exit(1)

    print(f"Анализирую {len(inputs)} файл(ов)...")
    with tempfile.TemporaryDirectory() as tmpdir:
        info = []
        for ubx in inputs:
            first, last, size = get_times(ubx, tmpdir)
            info.append({"path": ubx, "first": first, "last": last, "size": size})
            print(f"  {os.path.basename(ubx)}")
            print(f"    first: {first}")
            print(f"    last:  {last}")
            print(f"    size:  {size:,} байт")

        # Сортировка по first
        info.sort(key=lambda x: x["first"])

        # Проверка на перекрытия/разрывы
        print()
        print("Порядок слияния:")
        for i, item in enumerate(info):
            print(f"  {i+1}. {os.path.basename(item['path'])}  "
                  f"({item['first'].strftime('%m-%d %H:%M:%S')} → "
                  f"{item['last'].strftime('%m-%d %H:%M:%S')})")
            if i > 0:
                gap = (item["first"] - info[i-1]["last"]).total_seconds()
                if gap < -0.5:
                    print(f"     ⚠ ПЕРЕКРЫТИЕ: {abs(gap):.2f} с (порядок файлов может быть неверным)")
                elif gap > 1.0:
                    print(f"     ⚠ РАЗРЫВ: {gap:.2f} с")
                else:
                    print(f"     стык: gap {gap:+.3f} с")

        # Слияние
        with open(output, "wb") as out:
            total = 0
            for item in info:
                with open(item["path"], "rb") as f:
                    data = f.read()
                    out.write(data)
                    total += len(data)
        print()
        print(f"OK: {output} ({total:,} байт, из {len(info)} файла)")


if __name__ == "__main__":
    main()
