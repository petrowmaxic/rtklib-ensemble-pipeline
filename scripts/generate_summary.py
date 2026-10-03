#!/usr/bin/env python3
"""Генерирует статистику .pos в формате, похожем на GrafNav Processing Summary.
usage: generate_summary.py <in.pos> <out.txt> [--baseline-rover-x-y-z base-x-y-z]
"""
import sys, math
from datetime import datetime
from collections import defaultdict


def parse_pos(path):
    rows = []
    with open(path) as f:
        for line in f:
            if line.startswith('%') or not line.strip():
                continue
            p = line.split()
            if len(p) < 14:
                continue
            try:
                dt = datetime.strptime(f"{p[0]} {p[1]}", "%Y/%m/%d %H:%M:%S.%f")
                lat, lon, h, q = float(p[2]), float(p[3]), float(p[4]), int(p[5])
                ns = int(p[6])
                sdn, sde, sdu = float(p[7]), float(p[8]), float(p[9])
                # V10: формат .pos: date time lat lon h q ns sdn sde sdu sdne sdeu sdun age ratio
                # p[13] = age, p[14] = ratio
                ratio = float(p[14]) if len(p) >= 15 else 0.0
            except (ValueError, IndexError):
                continue
            rows.append(dict(dt=dt, lat=lat, lon=lon, h=h, q=q, ns=ns,
                             sdn=sdn, sde=sde, sdu=sdu, ratio=ratio))
    return rows


def rms(values):
    if not values:
        return 0.0
    return (sum(x*x for x in values) / len(values)) ** 0.5


def mean(values):
    if not values:
        return 0.0
    return sum(values) / len(values)


def compute_fwd_bwd_sep(ens_dirs):
    """FWD/BWD separation между e15_forward и e15_backward (Q=1).
    v1.3.1: агрегирует по всем сегментам.
    """
    import os as _os
    if isinstance(ens_dirs, str):
        ens_dirs = [ens_dirs]

    fwd = {}
    bwd = {}
    for d in ens_dirs:
        fp = _os.path.join(d, "e15_forward.pos")
        bp = _os.path.join(d, "e15_backward.pos")
        if _os.path.exists(fp):
            for r in parse_pos(fp):
                if r['q'] == 1:
                    fwd[r['dt']] = r
        if _os.path.exists(bp):
            for r in parse_pos(bp):
                if r['q'] == 1:
                    bwd[r['dt']] = r

    common = sorted(set(fwd) & set(bwd))
    if not common:
        return None

    dists = []
    for t in common:
        a, b = fwd[t], bwd[t]
        lat_mid = (a['lat'] + b['lat']) / 2.0
        e2 = 0.00669437999014
        N = 6378137.0 / math.sqrt(1 - e2 * math.sin(math.radians(lat_mid))**2)
        M = 6378137.0 * (1 - e2) / (1 - e2 * math.sin(math.radians(lat_mid))**2) ** 1.5
        dn = M * math.radians(b['lat'] - a['lat'])
        de = N * math.cos(math.radians(lat_mid)) * math.radians(b['lon'] - a['lon'])
        du = b['h'] - a['h']
        dists.append(math.sqrt(de*de + dn*dn + du*du))

    dists.sort()
    n = len(dists)
    med = dists[n//2]
    p90 = dists[int(0.9*n)]
    mx = dists[-1]
    if p90 < 2.0:
        status = "CLEAN"
    elif p90 < 10.0:
        status = "WATCH"
    else:
        status = "MANUAL_REVIEW"
    return dict(n=n, median=med, p90=p90, max=mx, status=status)


def _auto_ensemble_dir(pos_path):
    """Ищет ensemble/ или seg_N/ рядом с .pos. Возвращает список директорий."""
    import os as _os, glob as _glob
    d = _os.path.dirname(_os.path.abspath(pos_path))
    # classic: ensemble/
    ens = _os.path.join(d, "ensemble")
    if _os.path.isdir(ens) and _os.path.exists(_os.path.join(ens, "e15_forward.pos")):
        return [ens]
    # v1.3.0: seg_1/, seg_2/, ... — все сегменты
    segs = sorted(_glob.glob(_os.path.join(d, "seg_*")))
    if segs:
        valid = [s for s in segs if _os.path.isdir(s)
                 and _os.path.exists(_os.path.join(s, "e15_backward.pos"))]
        if valid:
            return valid
    return None


def _all_ensemble_dirs(pos_path):
    """Совместимость со старым API: возвращает одиночный dir или None."""
    r = _auto_ensemble_dir(pos_path)
    return r[0] if r else None


def compute_drift_vs_bwd(pos_path, ens_dirs):
    """Drift result vs backward (Q=1), агрегация по всем сегментам.
    v1.3.1: принимает список директорий.
    """
    import os as _os
    if isinstance(ens_dirs, str):
        ens_dirs = [ens_dirs]

    bwd_q1 = {}
    for d in ens_dirs:
        for cand_name in ("e15_backward.pos", "e17_backward.pos",
                          "e20_backward.pos", "e22_backward.pos"):
            bp = _os.path.join(d, cand_name)
            if _os.path.exists(bp):
                for r in parse_pos(bp):
                    if r['q'] == 1:
                        bwd_q1[r['dt']] = r
                break

    res_rows = parse_pos(pos_path)
    res_q1 = {r['dt']: r for r in res_rows if r['q'] == 1}
    n_q1 = len(res_q1)
    if n_q1 == 0:
        return None

    common = sorted(set(res_q1) & set(bwd_q1))
    if not common:
        return None

    dists = []
    for t in common:
        a, b = res_q1[t], bwd_q1[t]
        lat_mid = (a['lat'] + b['lat']) / 2.0
        e2 = 0.00669437999014
        N = 6378137.0 / math.sqrt(1 - e2 * math.sin(math.radians(lat_mid))**2)
        M = 6378137.0 * (1 - e2) / (1 - e2 * math.sin(math.radians(lat_mid))**2) ** 1.5
        dn = M * math.radians(b['lat'] - a['lat'])
        de = N * math.cos(math.radians(lat_mid)) * math.radians(b['lon'] - a['lon'])
        du = b['h'] - a['h']
        d = math.sqrt(de*de + dn*dn + du*du)
        dists.append(min(d, 500.0))
    dists.sort()
    n = len(dists)
    return dict(
        n_q1=n_q1,
        n_common=len(common),
        coverage=len(common) / n_q1,
        mean=sum(dists) / n,
        median=dists[n//2],
        p90=dists[int(0.9*n)],
    )


def main():
    if len(sys.argv) < 3:
        print("usage: generate_summary.py <in.pos> <out.txt>")
        sys.exit(1)
    pos_path = sys.argv[1]
    out_path = sys.argv[2]

    ens_dir = None
    if '--ensemble-dir' in sys.argv:
        try:
            ens_dir = sys.argv[sys.argv.index('--ensemble-dir') + 1]
        except IndexError:
            pass
    if not ens_dir:
        ens_dir = _auto_ensemble_dir(pos_path)

    rows = parse_pos(pos_path)
    if not rows:
        print("ERROR: нет данных в .pos")
        sys.exit(1)

    # Сортировка по времени — важно для backward-pos
    rows.sort(key=lambda r: r['dt'])

    n = len(rows)
    q_cnt = defaultdict(int)
    for r in rows:
        q_cnt[r['q']] += 1

    # Время
    first_dt = rows[0]['dt']
    last_dt = rows[-1]['dt']
    duration = (last_dt - first_dt).total_seconds()
    expected_10hz = int(duration * 10) + 1

    # SD-распределение (по sdu, как у GrafNav по общей SD)
    sd_bins = [(0, 0.10), (0.10, 0.30), (0.30, 1.00), (1.00, 5.00), (5.00, float('inf'))]
    sd_hist = defaultdict(int)
    for r in rows:
        # среднее SD по осям
        sd = (r['sdn'] + r['sde'] + r['sdu']) / 3
        for lo, hi in sd_bins:
            if lo <= sd < hi:
                sd_hist[(lo, hi)] += 1
                break

    # Baseline distances (если задан base ECEF)
    base_ecef = None
    if '--baseline-base-ecef' in sys.argv:
        idx = sys.argv.index('--baseline-base-ecef')
        try:
            base_ecef = (float(sys.argv[idx+1]), float(sys.argv[idx+2]), float(sys.argv[idx+3]))
        except (ValueError, IndexError):
            pass

    baseline_stats = None
    if base_ecef:
        distances = []
        for r in rows:
            # lat/lon/h → ECEF
            lat = math.radians(r['lat']); lon = math.radians(r['lon']); h = r['h']
            a = 6378137.0; f = 1/298.257223563; e2 = 2*f - f*f
            N = a / math.sqrt(1 - e2 * math.sin(lat)**2)
            x = (N + h) * math.cos(lat) * math.cos(lon)
            y = (N + h) * math.cos(lat) * math.sin(lon)
            z = (N*(1-e2) + h) * math.sin(lat)
            d = math.sqrt((x-base_ecef[0])**2 + (y-base_ecef[1])**2 + (z-base_ecef[2])**2)
            distances.append(d)
        if distances:
            baseline_stats = {
                'max': max(distances)/1000,
                'min': min(distances)/1000,
                'avg': sum(distances)/len(distances)/1000,
                'first': distances[0]/1000,
                'last': distances[-1]/1000,
            }

    # Записываем
    with open(out_path, 'w') as f:
        f.write("RTKLIB Processing Summary\n")
        f.write("Program: rnx2rtkp_EX (RTKLIB-EX 2.5.1)\n")
        f.write(f"Input: {pos_path.split('/')[-1]}\n")
        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

        f.write("Number of Epochs:\n")
        f.write(f"\tTotal in .pos:        \t{n}\n")
        f.write(f"\tQ=1 (fix):           \t{q_cnt.get(1,0)}  ({100*q_cnt.get(1,0)/n:.1f} %)\n")
        f.write(f"\tQ=2 (float):         \t{q_cnt.get(2,0)}  ({100*q_cnt.get(2,0)/n:.1f} %)\n")
        f.write(f"\tQ=4 (DGPS):          \t{q_cnt.get(4,0)}\n")
        f.write(f"\tQ=5 (single):        \t{q_cnt.get(5,0)}\n")
        f.write(f"\tQ=6 (PPP):           \t{q_cnt.get(6,0)}\n\n")

        f.write("Time Range:\n")
        f.write(f"\tFirst Epoch:         \t{first_dt.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}\n")
        f.write(f"\tLast Epoch:          \t{last_dt.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}\n")
        f.write(f"\tDuration:            \t{duration:.1f} s\n")
        f.write(f"\tExpected at 10 Hz:   \t{expected_10hz}\n")
        f.write(f"\tMissing (approx):    \t{max(0, expected_10hz - n)}  ({max(0, 100*(expected_10hz - n)/expected_10hz):.2f} %)\n\n")

        f.write("Quality Number Percentages:\n")
        f.write(f"\tQ 1:\t{100*q_cnt.get(1,0)/n:.1f} %\n")
        f.write(f"\tQ 2:\t{100*q_cnt.get(2,0)/n:.1f} %\n")
        f.write(f"\tQ 3:\t{100*q_cnt.get(3,0)/n:.1f} %\n")
        f.write(f"\tQ 4:\t{100*q_cnt.get(4,0)/n:.1f} %\n")
        f.write(f"\tQ 5:\t{100*q_cnt.get(5,0)/n:.1f} %\n")
        f.write(f"\tQ 6:\t{100*q_cnt.get(6,0)/n:.1f} %\n\n")

        f.write("Position Standard Deviation Percentages (avg of sdn/sde/sdu):\n")
        for lo, hi in sd_bins:
            cnt = sd_hist[(lo, hi)]
            if hi == float('inf'):
                f.write(f"\t{lo:.2f} m + over:\t{100*cnt/n:.1f} %\n")
            else:
                f.write(f"\t{lo:.2f} - {hi:.2f} m:\t{100*cnt/n:.1f} %\n")
        f.write("\n")

        if ens_dir:
            ens_dirs = ens_dir if isinstance(ens_dir, list) else [ens_dir]
            fb = compute_fwd_bwd_sep(ens_dirs)
            if fb:
                f.write("FWD/BWD Separation (e15 pair):\n")
                f.write(f"\tCommon Q=1 epochs:  \t{fb['n']}\n")
                f.write(f"\tMedian:             \t{fb['median']:.3f} m\n")
                f.write(f"\tP90:                \t{fb['p90']:.3f} m\n")
                f.write(f"\tMax:                \t{fb['max']:.3f} m\n")
                f.write(f"\tStatus:             \t{fb['status']}\n\n")

            dr = compute_drift_vs_bwd(pos_path, ens_dirs)
            if dr:
                if dr['coverage'] >= 0.85:
                    cov_s = "OK"
                elif dr['coverage'] >= 0.60:
                    cov_s = "WATCH"
                else:
                    cov_s = "ALERT"
                if dr['median'] < 0.05:
                    drift_s = "CLEAN"
                elif dr['median'] < 0.30:
                    drift_s = "WATCH"
                else:
                    drift_s = "DRIFT_HIGH"
                f.write("Drift vs Backward (Q=1):\n")
                f.write(f"\tQ=1 in result:      \t{dr['n_q1']}\n")
                f.write(f"\tQ=1 in both:        \t{dr['n_common']}\n")
                f.write(f"\tCoverage:           \t{100*dr['coverage']:.1f} % ({cov_s})\n")
                f.write(f"\tMean drift:         \t{dr['mean']:.3f} m ({drift_s})\n")
                f.write(f"\tMedian drift:       \t{dr['median']:.3f} m\n")
                f.write(f"\tP90 drift:          \t{dr['p90']:.3f} m\n\n")

        if baseline_stats:
            f.write("Baseline Distances:\n")
            f.write(f"\tMaximum:    \t{baseline_stats['max']:.3f} (km)\n")
            f.write(f"\tMinimum:    \t{baseline_stats['min']:.3f} (km)\n")
            f.write(f"\tAverage:    \t{baseline_stats['avg']:.3f} (km)\n")
            f.write(f"\tFirst Epoch:\t{baseline_stats['first']:.3f} (km)\n")
            f.write(f"\tLast Epoch: \t{baseline_stats['last']:.3f} (km)\n\n")

    print(f"OK: {out_path}")


if __name__ == '__main__':
    main()
