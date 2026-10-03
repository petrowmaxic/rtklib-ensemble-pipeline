# Приложение B. Листинги ключевых скриптов

## B.1. ensemble_viterbi.py — главный алгоритм

```python
#!/usr/bin/env python3
"""Ensemble merge Viterbi — глобальная оптимизация пути по кластерам.
Имитация ARTK REWIND через дискретную оптимизацию.

Параметры (env):
  ANCHOR_LAT, ANCHOR_LON, ANCHOR_H   — координата площадки
  ANCHOR_BONUS_MAX (10.0)            — макс. бонус за близость к anchor
  ANCHOR_SCALE (10.0)                — масштаб затухания бонуса (м)
  CLUSTER_THRESH_M (0.5)             — радиус кластеризации
  MAX_JUMP_M (10.0)                  — макс. путь за 0.1 сек
  MAX_GAP_SEC (2.0)                  — макс. разрыв между эпохами (сек)
"""
import sys, math, glob, os, time, bisect
from datetime import datetime


ANCHOR = {
    'lat': float(os.environ.get("ANCHOR_LAT", "61.161609573")),
    'lon': float(os.environ.get("ANCHOR_LON", "154.015098774")),
    'h':   float(os.environ.get("ANCHOR_H",   "832.4611")),
}
ANCHOR_BONUS_MAX = float(os.environ.get("ANCHOR_BONUS_MAX", "10.0"))
ANCHOR_SCALE = float(os.environ.get("ANCHOR_SCALE", "10.0"))
CLUSTER_THRESH_M = float(os.environ.get("CLUSTER_THRESH_M", "0.5"))
MAX_JUMP_M = float(os.environ.get("MAX_JUMP_M", "10.0"))
MAX_GAP_SEC = float(os.environ.get("MAX_GAP_SEC", "2.0"))


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


def ecef_dist(a, b):
    R = 6371000.0
    dlat = (a['lat'] - b['lat']) * math.pi / 180 * R
    dlon = (a['lon'] - b['lon']) * math.pi / 180 * R * math.cos(math.radians(a['lat']))
    dh = a['h'] - b['h']
    return math.sqrt(dlat*dlat + dlon*dlon + dh*dh)


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
    """Вес кластера: суммарное качество прогонов + бонус за близость к anchor."""
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
            max_jump = MAX_JUMP_M * max(1.0, gap / 0.1)
            dp_cur = []
            back_cur = []
            for j, (c_j, w_j, _, _) in enumerate(cands):
                best_score = -1e18
                best_k = -1
                for k, (c_k, _, _, _) in enumerate(prev_cands):
                    d = ecef_dist(c_j, c_k)
                    if d <= max_jump:
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

    result — список (center, votes, raw) или None для каждой эпохи.
    epochs — список (t, cands) для получения времени.
    max_gap_m — макс. допустимое расстояние между соседями (иначе оставляем как есть).
    """
    N = len(result)
    out = list(result)

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
                        # raw берём из любого доступного
                        raw = None
                        for idx in (prev_idx, next_idx):
                            r = result[idx]
                            if r and r[2]:
                                raw = r[2]
                                break
                        out[k] = ({'lat': lat, 'lon': lon, 'h': h}, 1, raw)
        i = j

    return out


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
    print(f"  Anchor: lat={ANCHOR['lat']:.9f} lon={ANCHOR['lon']:.9f} h={ANCHOR['h']:.4f}")

    # Собираем эпохи: список (t, [candidates])
    epochs = []
    n_skip = 0
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
            # Fallback — float из лучшего по качеству прогона
            best_idx = max(range(len(all_pos)), key=lambda k: run_quality[k])
            if t in all_pos[best_idx]:
                r = all_pos[best_idx][t]
                cands = [(r, 0.05, 0, r['raw'])]
            else:
                cands = [(dict(ANCHOR), 0.05, 0, None)]
            n_skip += 1
        epochs.append((t, cands))

    print(f"  [timer] сборка кластеров: {time.time() - t_parse:.2f} сек")
    print(f"  Эпох без fix (anchor fallback): {n_skip}")

    # Viterbi
    t_vit = time.time()
    result = viterbi_path(epochs)
    print(f"  [timer] Viterbi: {time.time() - t_vit:.2f} сек")

    # Интерполяция fallback-эпох
    t_interp = time.time()
    result = interpolate_gaps(result, epochs)
    n_interpolated = sum(1 for r in result if r is not None and r[1] == 1) - sum(1 for r in viterbi_path(epochs) if r is not None and r[1] > 0)
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
            extra = ' '.join(raw[6:]) if len(raw) > 6 else ""
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
```

## B.2. pipeline_ensemble.sh — запуск 8 прогонов

```bash
#!/usr/bin/env bash
# 8 прогонов (4 elmask × 2 soltype) для ensemble.
set -uo pipefail

ROVER="$1"; BASE_DIR="$2"; WORK="$3"

BIN="$HOME/gnss_experiment/bin/rnx2rtkp_EX"
CONF="$HOME/gnss_experiment/conf/FINAL.conf"
ECEF="-2772947.5700 1351588.2062 5564759.1253"
OUT="$WORK/ensemble"

mkdir -p "$OUT"
mkdir -p "$WORK/logs"

# 1. База
if [ ! -f "$WORK/base_surveyed.26O" ]; then
    UBX_LIST=()
    while IFS= read -r f; do UBX_LIST+=("$f"); done < <(find "$BASE_DIR" -maxdepth 1 -name '*.ubx' -type f ! -name 'merged*' | sort)
    [ ${#UBX_LIST[@]} -eq 0 ] && exit 1
    if [ ${#UBX_LIST[@]} -gt 1 ]; then
        python3 "$HOME/gnss_experiment/scripts/merge_ubx.py" "$WORK/base_merged.ubx" "${UBX_LIST[@]}" >/dev/null 2>&1
        BASE_UBX="$WORK/base_merged.ubx"
    else
        BASE_UBX="${UBX_LIST[0]}"
    fi
    "$HOME/gnss_experiment/bin/convbin_EX" -r ubx -o "$WORK/base.26O" -n "$WORK/base.26N" "$BASE_UBX" >/dev/null 2>&1
    python3 "$HOME/gnss_experiment/scripts/patch_approx_position.py" "$WORK/base.26O" $ECEF >/dev/null 2>&1
    cp "$WORK/base.26O" "$WORK/base_surveyed.26O"
fi

# 2. Ровер
# Проверяем не на "существует", а на "существует и не пуст"
if [ ! -s "$WORK/rover.26O" ]; then
    mkdir -p "$WORK/logs"
    cp "$ROVER" "$WORK/rover.NOV"
    cd "$WORK"
    # ОЧИСТКА: удалить temp-файлы и старые .26* перед запуском NovAtel Convert
    rm -f "$WORK"/rover.NOV_*temp_*.txt 2>/dev/null
    rm -f "$WORK"/rover.26[OGNCIJHL] 2>/dev/null
    rm -f "$WORK"/rover.80[OGNCIJHL] 2>/dev/null

    WINE="/Applications/CrossOver.app/Contents/SharedSupport/CrossOver/CrossOver-Hosted Application/wine"
    EXE="/Users/maxic/Library/Application Support/CrossOver/Bottles/Novatel converter/drive_c/Program Files/NovAtel Convert/NovAtelConvert.exe"
    "$WINE" "$EXE" -r3.03 rover.NOV > "$WORK/logs/novatel.log" 2>&1

    # Нормализация: ищем любой rover.NNO/.NNN и переименовываем в .26*
    NV_OBS=$(find "$WORK" -maxdepth 1 -name 'rover.[0-9][0-9]O' -type f ! -size 0 | head -1)
    NV_NAV=$(find "$WORK" -maxdepth 1 -name 'rover.[0-9][0-9]N' -type f ! -size 0 | head -1)
    if [ -n "$NV_OBS" ] && [ -n "$NV_NAV" ]; then
        [ "$NV_OBS" != "$WORK/rover.26O" ] && mv -f "$NV_OBS" "$WORK/rover.26O"
        [ "$NV_NAV" != "$WORK/rover.26N" ] && mv -f "$NV_NAV" "$WORK/rover.26N"
    fi

    # Fail fast
    if [ ! -s "$WORK/rover.26O" ]; then
        echo "[pipeline_ensemble] ERROR: rover.26O не создан для $ROVER" >&2
        echo "  Содержимое WORK:" >&2
        ls -la "$WORK" | head -20 >&2
        echo "  Лог NovAtel Convert (последние 30 строк):" >&2
        tail -30 "$WORK/logs/novatel.log" >&2
        exit 1
    fi
    echo "  ✓ rover.26O ($(wc -c < "$WORK/rover.26O" | tr -d ' ') байт)"
fi

# 3. 8 прогонов (параллельно, N_JOBS одновременно)
N_JOBS=${N_JOBS:-4}

run_one() {
    local EL="$1"
    local ST="$2"
    local NAME="e${EL}_${ST}"
    local POS="$OUT/$NAME.pos"
    local CONF_TMP="$OUT/$NAME.conf"
    local LOG="$WORK/logs/${NAME}.log"
    [ -s "$POS" ] && return 0
    sed "s/^pos1-elmask.*/pos1-elmask        =${EL}/; s/^pos1-soltype.*/pos1-soltype        =${ST}/" "$CONF" > "$CONF_TMP"
    "$BIN" -k "$CONF_TMP" -ti 0.10 -r $ECEF -o "$POS" \
        "$WORK/rover.26O" "$WORK/base_surveyed.26O" \
        "$WORK/rover.26N" "$WORK/base.26N" > "$LOG" 2>&1
}

for EL in 15 17 20 22; do
    for ST in forward backward; do
        run_one "$EL" "$ST" &
        while [ "$(jobs -r | wc -l | tr -d ' ')" -ge "$N_JOBS" ]; do
            sleep 0.3
        done
    done
done
wait
```

## B.3. export_v2.py — экспорт XYZ с DOP

```python
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


def parse_stat_by_index(stat_path):
    """Список (epoch_index, [(az, el), ...]) для каждой эпохи в порядке файла."""
    epochs = []           # список списков (az, el)
    current_sats = None
    with open(stat_path) as f:
        for line in f:
            if line.startswith('$POS,'):
                if current_sats is not None:
                    epochs.append(current_sats)
                current_sats = []
            elif line.startswith('$SAT,'):
                if current_sats is None:
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
                current_sats.append((az, el))
    if current_sats is not None:
        epochs.append(current_sats)
    return epochs


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
    stat_epochs = parse_stat_by_index(sys.argv[2])
    out_path = sys.argv[3]
    only_q1 = '--q1' in sys.argv

    print(f"  .pos : {len(pos)} эпох")
    print(f"  .stat: {len(stat_epochs)} эпох")

    # Если .pos в обратном порядке (backward) — разворачиваем и .pos, и .stat
    if len(pos) >= 2 and pos[0][0] > pos[-1][0]:
        print(f"  backward-порядок обнаружен, разворачиваю .pos и .stat")
        pos = pos[::-1]
        stat_epochs = stat_epochs[::-1]

    n = min(len(pos), len(stat_epochs))
    if len(pos) != len(stat_epochs):
        print(f"  ⚠ несовпадение длины: min={n}, берём первые {n}")

    header = "/ GPSDate     GPSTime      Longitude       Latitude    H-Ell      PDOP   HDOP   VDOP"
    n_written = 0
    n_dop_zero = 0
    with open(out_path, 'w', newline='\r\n') as f:
        f.write(header + '\n')
        for i in range(n):
            dt, lat, lon, h, q = pos[i]
            if only_q1 and q != 1:
                continue
            pdop, hdop, vdop = dop_from_sats(stat_epochs[i])
            if pdop == 0.0:
                n_dop_zero += 1
            date_s = dt.strftime('%Y/%m/%d')
            time_s = f"{dt.hour}:{dt.minute:02d}:{dt.second:02d}.{dt.microsecond//10000:02d}"
            f.write(f"{date_s}  {time_s} {lon:.10f}  {lat:.10f}      {h:.3f}   {pdop:.2f}   {hdop:.2f}   {vdop:.2f}\n")
            n_written += 1
    print(f"OK: {n_written} строк → {out_path}  (DOP=0: {n_dop_zero})")


if __name__ == '__main__':
    main()
```

## B.4. batch_ensemble.sh — batch 41 проекта

```bash
#!/usr/bin/env bash
# Батч: для каждого проекта — pipeline quiet (8 прогонов) + Viterbi + summary.
set -uo pipefail

ROVER_ROOT="/Users/maxic/Documents/1_Data.nosync/Julietta"
BASE_ROOT="/Users/maxic/Documents/2_Diff.nosync/Julietta"
WORK_ROOT="$HOME/gnss_batch_runs"
CSV="$WORK_ROOT/batch_results.csv"
ANCHOR_FILE="$HOME/gnss_experiment/conf/ANCHOR_Julietta.txt"

mkdir -p "$WORK_ROOT"

read -r ANCHOR_LAT ANCHOR_LON ANCHOR_H < "$ANCHOR_FILE"
export ANCHOR_LAT ANCHOR_LON ANCHOR_H

PROJECTS=(
  20260817_1 20260817_2 20260818_1 20260818_2 20260819_1 20260819_2
  20260821_1 20260821_2 20260822_1 20260822_2 20260823_1 20260823_2
  20260825_1 20260825_2 20260826_1 20260826_2 20260828_1 20260828_2
  20260829_1 20260829_2 20260830_1 20260830_2 20260831_1 20260831_2
  20260901_1 20260901_2 20260902 20260905 20260906_1 20260906_2
  20260913 20260914_1 20260914_2 20260915 20260916 20260917_1
  20260918_1 20260918_2 20260920 20260921_1 20260921_2
  20260922_1 20260922_2 20260922_3 20260922_4
)

echo "project,n_epochs,Q1,Q1_pct,mean_dH_cm,median_dH_cm,mean_all_cm,status" > "$CSV"

BATCH_TOTAL=${#PROJECTS[@]}
IDX=0
BATCH_START=$(date +%s)

for PROJ in "${PROJECTS[@]}"; do
    IDX=$((IDX + 1))
    ELAPSED=$(( $(date +%s) - BATCH_START ))
    printf '\n[%02d/%02d] ════════════════════════════════════════\n' "$IDX" "$BATCH_TOTAL"
    printf '         %s   (прошло: %d мин)\n' "$PROJ" "$((ELAPSED / 60))"
    printf '════════════════════════════════════════\n' '' 2>/dev/null || true
    DATE="${PROJ:0:8}"
    ROVER_DIR="$ROVER_ROOT/$PROJ"
    ROVER_NOV="$ROVER_DIR/$PROJ.NOV"
    BASE_DIR="$BASE_ROOT/$DATE"
    WORK="$WORK_ROOT/$PROJ"

    # Проверка ровера
    if [ ! -f "$ROVER_NOV" ]; then
        echo "  [skip] $PROJ — нет $ROVER_NOV"
        echo "$PROJ,,,,,,,skip_no_rover" >> "$CSV"
        continue
    fi

    # Проверка базы: директория + хотя бы один .ubx
    if [ ! -d "$BASE_DIR" ]; then
        echo "  [skip] $PROJ — нет директории базы $BASE_DIR"
        echo "$PROJ,,,,,,,skip_no_base_dir" >> "$CSV"
        continue
    fi
    N_UBX=$(find "$BASE_DIR" -maxdepth 1 -name '*.ubx' -type f ! -name 'merged*' | wc -l | tr -d ' ')
    if [ "$N_UBX" -eq 0 ]; then
        echo "  [skip] $PROJ — нет .ubx в $BASE_DIR"
        echo "$PROJ,,,,,,,skip_no_ubx" >> "$CSV"
        continue
    fi

    # Прогресс уже напечатан выше

    # 1. Прогон 8 конфигураций (idempotent — pipeline_ensemble пропустит готовые .pos)
    mkdir -p "$WORK"
    "$HOME/gnss_experiment/scripts/pipeline_ensemble.sh" "$ROVER_NOV" "$BASE_DIR" "$WORK" || {
        echo "$PROJ,,,,,,,fail_pipeline" >> "$CSV"
        continue
    }

    # 2. Viterbi
    VIT="$WORK/ensemble_viterbi.pos"

    # Проверка: есть ли хотя бы один непустой .pos
    N_POS=$(find "$WORK/ensemble" -maxdepth 1 -name '*.pos' -type f ! -name '*_events*' -size +1k 2>/dev/null | wc -l | tr -d ' ')
    if [ "$N_POS" -lt 4 ]; then
        echo "  [skip] $PROJ — только $N_POS валидных ensemble .pos (нужно >= 4)"
        echo "$PROJ,,,,,,,skip_bad_ensemble" >> "$CSV"
        continue
    fi

    # Удалить старый пустой Viterbi если есть
    [ -f "$VIT" ] && rm -f "$VIT"
    python3 "$HOME/gnss_experiment/scripts/ensemble_viterbi.py" "$WORK/ensemble" "$VIT" 2>&1 | tee -a "$WORK/logs/viterbi.log"

    if [ ! -s "$VIT" ] || [ "$(grep -c '^20' "$VIT")" -lt 100 ]; then
        echo "  [skip] $PROJ — пустой Viterbi"
        echo "$PROJ,,,,,,,empty_viterbi" >> "$CSV"
        continue
    fi

    # 3. Анализ
    POS="$VIT"
    XYZ_GNSS="$ROVER_DIR/$PROJ.xyz"

    # Проверка на пустой результат
    if [ ! -s "$POS" ] || [ "$(grep -c '^20' "$POS")" -lt 100 ]; then
        echo "  [skip] $PROJ — пустой Viterbi pos"
        echo "$PROJ,,,,,,,empty_viterbi" >> "$CSV"
        continue
    fi

    read -r TOTAL Q1 Q1PCT <<< "$(LC_NUMERIC=C awk '!/^%/{n++; if($6==1) q1++} END{if(n>0) printf "%d %d %.2f", n, q1+0, 100*q1/n; else print "0 0 0"}' "$POS")"
    MEAN_DH=""; MED_DH=""; MEAN_ALL=""
    if [ -f "$XYZ_GNSS" ]; then
        RES=$(cd "$HOME/gnss_experiment" && python3 scripts/compare_q1.py "$POS" "$XYZ_GNSS" "batch" 2>/dev/null)
        MEAN_ALL=$(echo "$RES" | awk '/--- ВСЕ ЭПОХИ/{p=1} p && /^  dH/{split($0,a,"mean="); split(a[2],b," "); print b[1]; exit}')
        MEAN_DH=$(echo "$RES" | awk '/--- ТОЛЬКО Q=1/{p=1} p && /^  dH/{split($0,a,"mean="); split(a[2],b," "); print b[1]; exit}')
        MED_DH=$(echo "$RES" | awk '/--- ТОЛЬКО Q=1/{p=1} p && /^  dH/{split($0,a,"median="); split(a[2],b," "); print b[1]; exit}')
    fi

    echo "  Q1=$Q1PCT%  mean_all=$MEAN_ALL  mean_Q1=$MEAN_DH  median_Q1=$MED_DH"
    echo "$PROJ,$TOTAL,$Q1,$Q1PCT,$MEAN_DH,$MED_DH,$MEAN_ALL,ok" >> "$CSV"
done

echo
echo "══════════════════════════════════"
echo "  ИТОГИ: $CSV"
cat "$CSV"
```
