#!/usr/bin/env python3
"""Ensemble merge Viterbi — глобальная оптимизация пути по кластерам.
Имитация ARTK REWIND через дискретную оптимизацию.

Параметры (env):
  ANCHOR_LAT, ANCHOR_LON, ANCHOR_H   — координата площадки
  ANCHOR_BONUS_MAX (0.5)            — макс. бонус за близость к anchor
  ANCHOR_SCALE (10.0)                — масштаб затухания бонуса (м)
  CLUSTER_THRESH_M (0.5)             — радиус кластеризации
  MAX_JUMP_M (10.0)                  — макс. горизонтальный путь за 0.1 сек
  MAX_JUMP_H_M (100.0)               — макс. разница по высоте (AR-ветка)
  MAX_GAP_SEC (2.0)                  — макс. разрыв между эпохами (сек)

v1.2.0: проверка прыжка раздельная — гориз (MAX_JUMP_M) и верт (MAX_JUMP_H_M).
  Причина: 3D-метрика симметрично наказывала h, из-за чего после потери
  backward-кластера Viterbi не мог вернуться (h-разница ~100 м > 10 м).
"""
import sys, math, glob, os, time, bisect
from datetime import datetime


# V11 (2026-09-26): anchor опционален.
ANCHOR_REQUIRED = False
_a_lat = os.environ.get("ANCHOR_LAT")
_a_lon = os.environ.get("ANCHOR_LON")
_a_h   = os.environ.get("ANCHOR_H")
ANCHOR = None
if _a_lat and _a_lon and _a_h:
    ANCHOR = {
        'lat': float(_a_lat),
        'lon': float(_a_lon),
        'h':   float(_a_h),
    }
elif any([_a_lat, _a_lon, _a_h]):
    print("WARN: задана только часть ANCHOR_*, игнорирую anchor.", file=sys.stderr)
ANCHOR_BONUS_MAX = float(os.environ.get("ANCHOR_BONUS_MAX", "0.5"))
ANCHOR_SCALE = float(os.environ.get("ANCHOR_SCALE", "10.0"))
CLUSTER_THRESH_M = float(os.environ.get("CLUSTER_THRESH_M", "0.5"))
MAX_JUMP_M = float(os.environ.get("MAX_JUMP_M", "10.0"))
MAX_GAP_SEC = float(os.environ.get("MAX_GAP_SEC", "2.0"))
# v1.2.0: раздельная проверка прыжка. Гориз ограничен физикой полёта,
# верт — только реальной разницей между AR-ветками (обычно <100 м).
MAX_JUMP_H_M = float(os.environ.get("MAX_JUMP_H_M", "100.0"))


def parse_pos(path):
    rows = {}
    with open(path) as f:
        for line in f:
            if line.startswith('%') or not line.strip():
                continue
            p = line.split()
            if len(p) < 15:
                continue
            try:
                dt = datetime.strptime(f"{p[0]} {p[1]}", "%Y/%m/%d %H:%M:%S.%f")
                lat, lon, h, q = float(p[2]), float(p[3]), float(p[4]), int(p[5])
            except (ValueError, IndexError):
                continue
            rows[dt] = dict(dt=dt, lat=lat, lon=lon, h=h, q=q, raw=p)
    return rows


WGS84_A = 6378137.0
WGS84_F = 1.0 / 298.257223563
WGS84_E2 = 2*WGS84_F - WGS84_F*WGS84_F


def _wgs84_radii(lat_deg):
    lat = math.radians(lat_deg)
    sin2 = math.sin(lat) ** 2
    N = WGS84_A / math.sqrt(1 - WGS84_E2 * sin2)
    M = WGS84_A * (1 - WGS84_E2) / (1 - WGS84_E2 * sin2) ** 1.5
    return M, N


def ecef_dist(a, b):
    lat_mid = (a['lat'] + b['lat']) / 2.0
    M, N = _wgs84_radii(lat_mid)
    dlat_rad = math.radians(b['lat'] - a['lat'])
    dlon_rad = math.radians(b['lon'] - a['lon'])
    dn = M * dlat_rad
    de = N * math.cos(math.radians(lat_mid)) * dlon_rad
    du = b['h'] - a['h']
    return math.sqrt(de*de + dn*dn + du*du)


def horiz_dist(a, b):
    """Горизонтальное расстояние (dn, de) между двумя dicts с lat/lon/h."""
    R = 6371000
    lat_mid = (a['lat'] + b['lat']) / 2.0
    dlat = math.radians(b['lat'] - a['lat'])
    dlon = math.radians(b['lon'] - a['lon'])
    x = dlon * math.cos(math.radians(lat_mid))
    return math.sqrt((dlat * R) ** 2 + (x * R) ** 2)


def cluster_fixes(fixes):
    """fixes — list of dicts with 'lat','lon','h'. Returns clusters as list of indices."""
    n = len(fixes)
    if n == 0:
        return []
    used = [False] * n
    clusters = []
    for i in range(n):
        if used[i]:
            continue
        cl = [i]
        used[i] = True
        for j in range(i+1, n):
            if used[j]:
                continue
            if ecef_dist(fixes[i], fixes[j]) < CLUSTER_THRESH_M:
                cl.append(j)
                used[j] = True
        clusters.append(cl)
    return clusters


def cluster_center(fixes, indices):
    n = len(indices)
    return {
        'lat': sum(fixes[i]['lat'] for i in indices) / n,
        'lon': sum(fixes[i]['lon'] for i in indices) / n,
        'h':   sum(fixes[i]['h']   for i in indices) / n,
    }


def weight_of(center, size, quality_sum):
    """Вес кластера: суммарное качество прогонов + бонус за близость к anchor.
    Если ANCHOR не задан — bonus=0."""
    if ANCHOR is None:
        return quality_sum
    d = ecef_dist(center, ANCHOR)
    bonus = ANCHOR_BONUS_MAX / (1.0 + d / ANCHOR_SCALE)
    return quality_sum + bonus


def viterbi_path(epochs):
    """epochs — список (t, [(center, weight, votes, raw), ...]).
    Возвращает для каждой эпохи (center, votes, raw) или None.
    Корректный Viterbi с segment-aware backtracking.
    """
    N = len(epochs)
    if N == 0:
        return []

    dp = []
    back = []

    # Первая эпоха
    t0, cands0 = epochs[0]
    if not cands0:
        dp.append([]); back.append([])
    else:
        dp.append([c[1] for c in cands0])
        back.append([-1] * len(cands0))

    prev_t = t0

    for i in range(1, N):
        t, cands = epochs[i]
        if not cands:
            dp.append([]); back.append([])
            prev_t = t
            continue

        gap = (t - prev_t).total_seconds()
        prev_cands = epochs[i-1][1]
        dp_prev = dp[-1]

        if gap > MAX_GAP_SEC or not prev_cands or not dp_prev:
            # Нет связи — новый сегмент
            dp.append([c[1] for c in cands])
            back.append([-1] * len(cands))
        else:
            max_jump = min(MAX_JUMP_M * max(1.0, gap / 0.1), 50.0)  # гориз, cap 50 м
            max_jump_h = min(MAX_JUMP_H_M * max(1.0, gap / 0.1), 500.0)  # v1.2.0, cap 500 м
            dp_cur = []
            back_cur = []
            for j, (c_j, w_j, _, _) in enumerate(cands):
                best_score = -1e18
                best_k = -1
                for k, (c_k, _, _, _) in enumerate(prev_cands):
                    # v1.2.0: раздельная проверка — гориз. и верт. независимо
                    d_horiz = horiz_dist(c_j, c_k)
                    d_h = abs(c_j['h'] - c_k['h'])
                    if d_horiz <= max_jump and d_h <= max_jump_h:
                        score = dp_prev[k] + w_j
                        if score > best_score:
                            best_score = score
                            best_k = k
                if best_k < 0:
                    best_score = w_j
                dp_cur.append(best_score)
                back_cur.append(best_k)
            dp.append(dp_cur)
            back.append(back_cur)

        prev_t = t

    # Backtracking: идём от последней эпохи назад, при разрыве — новый endpoint
    path = [None] * N
    i = N - 1
    while i >= 0:
        if not dp[i]:
            i -= 1
            continue
        j = max(range(len(dp[i])), key=lambda jj: dp[i][jj])
        while i >= 0 and j is not None and 0 <= j < len(back[i]):
            path[i] = j
            prev_j = back[i][j]
            i -= 1
            if prev_j is None or prev_j < 0:
                break
            j = prev_j

    # Формируем результат
    result = []
    for i in range(N):
        j = path[i]
        if j is None or j < 0 or j >= len(epochs[i][1]):
            result.append(None)
        else:
            c, w, v, raw = epochs[i][1][j]
            result.append((c, v, raw))
    return result


def interpolate_gaps(result, epochs, max_gap_m=500.0):
    """Линейная интерполяция fallback-эпох между соседними Q=1.
    Возвращает (out, n_interpolated).

    result — список (center, votes, raw) или None для каждой эпохи.
    epochs — список (t, cands) для получения времени.
    max_gap_m — макс. допустимое расстояние между соседями (иначе оставляем как есть).
    """
    N = len(result)
    out = list(result)
    n_interpolated = 0

    i = 0
    while i < N:
        if result[i] is not None and result[i][1] > 0:
            i += 1
            continue
        # Начало gap
        j = i
        while j < N and (result[j] is None or result[j][1] == 0):
            j += 1
        # gap [i, j-1]
        # Ищем предыдущий fix: i-1
        # Ищущий следующий fix: j
        prev_idx = i - 1 if i > 0 and result[i-1] is not None and result[i-1][1] > 0 else None
        next_idx = j if j < N and result[j] is not None and result[j][1] > 0 else None

        if prev_idx is not None and next_idx is not None:
            c1 = result[prev_idx][0]
            c2 = result[next_idx][0]
            # Проверяем расстояние
            d = ecef_dist(c1, c2)
            if d <= max_gap_m:
                t1 = epochs[prev_idx][0]
                t2 = epochs[next_idx][0]
                total_dt = (t2 - t1).total_seconds()
                if total_dt > 0:
                    for k in range(i, j):
                        tk = epochs[k][0]
                        frac = (tk - t1).total_seconds() / total_dt
                        lat = c1['lat'] + frac * (c2['lat'] - c1['lat'])
                        lon = c1['lon'] + frac * (c2['lon'] - c1['lon'])
                        h = c1['h'] + frac * (c2['h'] - c1['h'])
                        # raw берём из любого доступного (dict с 'raw' или list)
                        raw = None
                        for idx in (prev_idx, next_idx):
                            r = result[idx]
                            if r and r[2] is not None:
                                raw = r[2]
                                break
                        out[k] = ({'lat': lat, 'lon': lon, 'h': h}, 1, raw)
                        n_interpolated += 1
        i = j

    return out, n_interpolated


def _extract_raw(raw):
    """Извлекает список полей (15 элементов) из разных форматов:
    - dict из parse_pos: {'dt':..., 'lat':..., ..., 'raw': [...]}
    - list (готовый split)
    - None
    """
    if raw is None:
        return None
    if isinstance(raw, dict) and 'raw' in raw:
        return raw['raw']
    if isinstance(raw, list):
        return raw
    return None


def main():
    t_start = time.time()
    if len(sys.argv) < 3:
        print("usage: ensemble_viterbi.py <ensemble_dir> <out.pos>")
        sys.exit(1)
    ens_dir = sys.argv[1]
    out_path = sys.argv[2]

    all_files = glob.glob(os.path.join(ens_dir, "*.pos"))
    pos_files = sorted([p for p in all_files if "_events" not in os.path.basename(p)])
    print(f"  Прогонов: {len(pos_files)}")

    t_parse = time.time()
    all_pos = [parse_pos(p) for p in pos_files]
    print(f"  [timer] parse: {time.time() - t_parse:.2f} сек")

    # Per-run global quality (Q1 rate)
    run_quality = []
    for d in all_pos:
        if len(d) == 0:
            run_quality.append(0.0); continue
        q1 = sum(1 for r in d.values() if r['q'] == 1)
        run_quality.append(q1 / len(d))
    print(f"  Run qualities: {['%.3f' % q for q in run_quality]}")

    all_times = sorted(set().union(*[set(d.keys()) for d in all_pos]))
    print(f"  Уникальных эпох: {len(all_times)}")
    if ANCHOR is None:
        print("  Anchor: НЕ ЗАДАН (bonus=0)")
    else:
        print(f"  Anchor: lat={ANCHOR['lat']:.9f} lon={ANCHOR['lon']:.9f} h={ANCHOR['h']:.4f}")

    # Собираем эпохи: список (t, [candidates])
    epochs = []
    n_skip_float = 0
    n_skip_anchor = 0
    n_skip_empty = 0
    for t in all_times:
        # fixes: список (run_idx, coord_dict)
        fixes_with_run = []
        for run_idx, d in enumerate(all_pos):
            if t in d and d[t]['q'] == 1:
                fixes_with_run.append((run_idx, d[t]))
        fixes = [f for _, f in fixes_with_run]
        clusters = cluster_fixes(fixes)
        cands = []
        for c in clusters:
            center = cluster_center(fixes, c)
            votes = len(c)
            # Суммарное качество прогонов, попавших в этот кластер
            quality_sum = sum(run_quality[fixes_with_run[idx][0]] for idx in c)
            w = weight_of(center, votes, quality_sum)
            cands.append((center, w, votes, fixes[c[0]]))
        if not cands:
            best_idx = max(range(len(all_pos)), key=lambda k: run_quality[k])
            if t in all_pos[best_idx]:
                r = all_pos[best_idx][t]
                cands = [(r, 0.05, 0, r['raw'])]
                n_skip_float += 1
            elif ANCHOR is not None:
                cands = [(dict(ANCHOR), 0.05, 0, None)]
                n_skip_anchor += 1
            else:
                n_skip_empty += 1
                epochs.append((t, []))
                continue
        epochs.append((t, cands))

    print(f"  [timer] сборка кластеров: {time.time() - t_parse:.2f} сек")
    print(f"  Эпох без fix — float fallback:  {n_skip_float}")
    print(f"  Эпох без fix — anchor fallback: {n_skip_anchor}")
    print(f"  Эпох без fix — пропущено:       {n_skip_empty}")

    # Viterbi
    t_vit = time.time()
    result = viterbi_path(epochs)
    print(f"  [timer] Viterbi: {time.time() - t_vit:.2f} сек")

    # Интерполяция fallback-эпох
    t_interp = time.time()
    result, n_interpolated = interpolate_gaps(result, epochs)
    print(f"  [timer] интерполяция: {time.time() - t_interp:.2f} сек")

    # Запись
    n_q1 = 0
    n_written = 0
    with open(out_path, 'w') as f_out:
        with open(pos_files[0]) as f_in:
            for line in f_in:
                if line.startswith('%'):
                    f_out.write(line)
                else:
                    break
        for i, (t, _) in enumerate(epochs):
            r = result[i]
            if r is None:
                continue
            center, votes, raw = r
            if raw is None:
                for d in all_pos:
                    if t in d:
                        raw = d[t]['raw']
                        break
                else:
                    raw = ['x'] * 15
            q_final = 1 if votes > 0 else 2
            if q_final == 1:
                n_q1 += 1
            date_s = t.strftime('%Y/%m/%d')
            time_s = t.strftime('%H:%M:%S.%f')[:-3]
            raw_p = _extract_raw(raw)
            if raw_p is None:
                raw_p = ['x'] * 15
            extra = ' '.join(raw_p[6:]) if len(raw_p) > 6 else ""
            f_out.write(f"{date_s} {time_s}  {center['lat']:14.9f}  {center['lon']:14.9f}  {center['h']:10.4f}  {q_final}  {extra}\n")
            n_written += 1

    print()
    print(f"  Записано: {n_written}")
    print(f"  Q=1: {n_q1}")
    print(f"  Q=2: {n_written - n_q1}")
    if n_written:
        print(f"  Q1 процент: {100*n_q1/n_written:.2f}%")
    print(f"  [timer] ИТОГО: {time.time() - t_start:.2f} сек")


if __name__ == '__main__':
    main()
