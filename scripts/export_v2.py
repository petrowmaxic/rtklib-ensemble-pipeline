#!/usr/bin/env python3
"""Экспорт .pos + .stat → Oasis XYZ. Сопоставление по номеру эпохи,
а не по TOW (TOW может быть нормирован по-разному в forward/backward).

usage: export_v2.py <in.pos> <in.stat> <out.xyz> [--q1]
"""
import sys, math
from datetime import datetime


def parse_pos(path):
    """Список (dt, lat, lon, h, q) в порядке файла."""
    out = []
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
            out.append((dt, lat, lon, h, q))
    return out


def inv4(M):
    A = [row[:] + [1.0 if i == j else 0.0 for j in range(4)] for i, row in enumerate(M)]
    for col in range(4):
        piv = max(range(col, 4), key=lambda r: abs(A[r][col]))
        if abs(A[piv][col]) < 1e-12:
            return None
        A[col], A[piv] = A[piv], A[col]
        pv = A[col][col]
        for j in range(8):
            A[col][j] /= pv
        for r in range(4):
            if r == col:
                continue
            fct = A[r][col]
            if fct == 0.0:
                continue
            for j in range(8):
                A[r][j] -= fct * A[col][j]
    return [row[4:] for row in A]


GPS_EPOCH = datetime(1980, 1, 6)


def parse_stat_by_tow(stat_path):
    """Возвращает dict: datetime -> [(az, el), ...] для vsat=1.
    Парсит week + tow из $POS, конвертирует в datetime (GPST)."""
    from datetime import timedelta
    out = {}
    cur_week = None
    cur_tow = None
    cur_sats = None

    def flush():
        if cur_week is not None and cur_sats is not None:
            try:
                dt = GPS_EPOCH + timedelta(weeks=cur_week, seconds=cur_tow)
                out[dt] = cur_sats
            except Exception:
                pass

    with open(stat_path) as f:
        for line in f:
            if line.startswith('$POS,'):
                flush()
                p = line.rstrip().split(',')
                try:
                    cur_week = int(p[1])
                    cur_tow = float(p[2])
                except (ValueError, IndexError):
                    cur_week = None
                    cur_tow = None
                cur_sats = []
            elif line.startswith('$SAT,'):
                if cur_sats is None:
                    continue
                p = line.rstrip().split(',')
                if len(p) < 10:
                    continue
                try:
                    az = float(p[5]); el = float(p[6]); vsat = int(p[9])
                except (ValueError, IndexError):
                    continue
                if vsat != 1:
                    continue
                cur_sats.append((az, el))
    flush()
    return out


def dop_from_sats(sats):
    if len(sats) < 4:
        return (0.0, 0.0, 0.0)
    A = []
    for az_deg, el_deg in sats:
        az = math.radians(az_deg); el = math.radians(el_deg)
        A.append([math.cos(el)*math.sin(az), math.cos(el)*math.cos(az),
                  math.sin(el), 1.0])
    n = len(A)
    N = [[sum(A[k][i]*A[k][j] for k in range(n)) for j in range(4)] for i in range(4)]
    Q = inv4(N)
    if Q is None:
        return (0.0, 0.0, 0.0)
    return (math.sqrt(max(Q[0][0]+Q[1][1]+Q[2][2], 0)),
            math.sqrt(max(Q[0][0]+Q[1][1], 0)),
            math.sqrt(max(Q[2][2], 0)))


def main():
    if len(sys.argv) < 4:
        print("usage: export_v2.py <in.pos> <in.stat> <out.xyz> [--q1]")
        sys.exit(1)
    pos = parse_pos(sys.argv[1])
    dop_map = parse_stat_by_tow(sys.argv[2])
    out_path = sys.argv[3]
    only_q1 = '--q1' in sys.argv

    print(f"  .pos : {len(pos)} эпох")
    print(f"  .stat: {len(dop_map)} эпох (по week+tow)")

    # Сортировка .pos по времени (если пришёл в backward)
    if len(pos) >= 2 and pos[0][0] > pos[-1][0]:
        print(f"  backward-порядок .pos, разворачиваю")
        pos = pos[::-1]

    # --- Сопоставление по datetime ---
    pos_dict = {r[0]: r for r in pos}
    common = sorted(set(pos_dict) & set(dop_map))
    missing = len(pos_dict) - len(common)
    print(f"  общих эпох: {len(common)}  (без DOP: {missing})")

    header = "/ GPSDate     GPSTime      Longitude       Latitude    H-Ell      PDOP   HDOP   VDOP"
    n_written = 0
    n_dop_zero = 0
    with open(out_path, 'w', newline='\r\n') as f:
        f.write(header + '\n')
        for dt in common:
            _, lat, lon, h, q = pos_dict[dt]
            if only_q1 and q != 1:
                continue
            pdop, hdop, vdop = dop_from_sats(dop_map[dt])
            if pdop == 0.0:
                n_dop_zero += 1
            date_s = dt.strftime('%Y/%m/%d')
            time_s = f"{dt.hour}:{dt.minute:02d}:{dt.second:02d}.{dt.microsecond//10000:02d}"
            f.write(f"{date_s}  {time_s} {lon:.10f}  {lat:.10f}      {h:.3f}   {pdop:.2f}   {hdop:.2f}   {vdop:.2f}\n")
            n_written += 1
    print(f"OK: {n_written} строк → {out_path}  (DOP=0: {n_dop_zero})")


if __name__ == '__main__':
    main()
