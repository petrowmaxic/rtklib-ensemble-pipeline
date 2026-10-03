#!/usr/bin/env bash
# Получить anchor из готовых RINEX в WORK_DIR.
# usage: auto_anchor_from_workdir.sh <work_dir> [out_file]
set -uo pipefail

WORK="$1"
OUTFILE="${2:-}"
EXPERIMENT="$HOME/gnss_experiment"
ECEF="-2772947.5700 1351588.2062 5564759.1253"

[ -s "$WORK/rover.26O" ] || { echo "ERROR: нет rover.26O в $WORK" >&2; exit 1; }
[ -s "$WORK/base_surveyed.26O" ] || { echo "ERROR: нет base_surveyed.26O" >&2; exit 1; }

STATIC_POS="$WORK/static_anchor.pos"
"$EXPERIMENT/bin/rnx2rtkp_EX" -k "$EXPERIMENT/conf/STATIC.conf" -ti 1.0 \
    -r $ECEF \
    -o "$STATIC_POS" \
    "$WORK/rover.26O" "$WORK/base_surveyed.26O" \
    "$WORK/rover.26N" "$WORK/base.26N" >/dev/null 2>&1

[ -s "$STATIC_POS" ] || { echo "ERROR: static.pos пустой" >&2; exit 1; }

N=$(grep -c '^20' "$STATIC_POS")
if [ "$N" -lt 100 ]; then
    echo "ERROR: слишком мало эпох ($N), нужно >= 100" >&2
    exit 1
fi

# Velocity filter: усредняем только эпохи, где ровер покоится.
# Критерий: разница высоты до соседней эпохи < 5 см (v_h < 0.5 м/с при 10 Гц).
read -r LAT LON H N_EPOCH < <(LC_NUMERIC=C awk '
  function abs(x){return x<0?-x:x}
  !/^%/{
    if (prev_h != "") {
      dh = abs($5 - prev_h)
      if (dh < 0.05) {
        n++; slat+=$3; slon+=$4; sh+=$5
      }
    }
    prev_h = $5
  }
  END{
    if (n >= 100)
      printf "%.9f %.9f %.4f %d", slat/n, slon/n, sh/n, n
    else
      printf "0 0 0 %d", n
  }' "$STATIC_POS")

if [ "$LAT" = "0" ]; then
    echo "ERROR: не найдено >=100 стационарных эпох (v < 0.5 м/с). Файл может не содержать прогрев." >&2
    exit 1
fi

ANCHOR_LINE="$LAT $LON $H"

if [ -n "$OUTFILE" ]; then
    echo "$ANCHOR_LINE" > "$OUTFILE"
fi

echo "$ANCHOR_LINE"
