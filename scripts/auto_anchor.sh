#!/usr/bin/env bash
# Автоматическое получение anchor из прогрева ровера.
# usage: auto_anchor.sh <rover_progrev.NOV> <base_dir_or_ubx>
set -uo pipefail

ROVER="$1"
BASE_ARG="$2"
EXPERIMENT="$HOME/gnss_experiment"
WORK="$HOME/gnss_anchor_auto_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$WORK"

ECEF="-2772947.5700 1351588.2062 5564759.1253"
WINE="/Applications/CrossOver.app/Contents/SharedSupport/CrossOver/CrossOver-Hosted Application/wine"
EXE="/Users/maxic/Library/Application Support/CrossOver/Bottles/Novatel converter/drive_c/Program Files/NovAtel Convert/NovAtelConvert.exe"

echo "[1/5] База → RINEX"
UBX_LIST=()
while IFS= read -r f; do UBX_LIST+=("$f"); done < <(find "$BASE_ARG" -maxdepth 1 -name '*.ubx' -type f ! -name 'merged*' 2>/dev/null | sort)
if [ ${#UBX_LIST[@]} -eq 0 ] && [ -f "$BASE_ARG" ]; then UBX_LIST=("$BASE_ARG"); fi

if [ ${#UBX_LIST[@]} -gt 1 ]; then
    python3 "$EXPERIMENT/scripts/merge_ubx.py" "$WORK/base_merged.ubx" "${UBX_LIST[@]}" >/dev/null 2>&1
    BASE_UBX="$WORK/base_merged.ubx"
else
    BASE_UBX="${UBX_LIST[0]}"
fi

"$EXPERIMENT/bin/convbin_EX" -r ubx -o "$WORK/base.26O" -n "$WORK/base.26N" "$BASE_UBX" >/dev/null 2>&1
python3 "$EXPERIMENT/scripts/patch_approx_position.py" "$WORK/base.26O" $ECEF >/dev/null 2>&1
cp "$WORK/base.26O" "$WORK/base_surveyed.26O"

echo "[2/5] Ровер → RINEX"
cp "$ROVER" "$WORK/rover.NOV"
cd "$WORK"
"$WINE" "$EXE" -r3.03 rover.NOV >/dev/null 2>&1
[ -f rover.80O ] && [ ! -s rover.26O ] && mv rover.80O rover.26O
[ -f rover.80N ] && [ ! -s rover.26N ] && mv rover.80N rover.26N

if [ ! -s "$WORK/rover.26O" ]; then
    echo "ERROR: rover.26O пустой"; exit 1
fi

echo "[3/5] Static-обработка"
"$EXPERIMENT/bin/rnx2rtkp_EX" -k "$EXPERIMENT/conf/STATIC.conf" -ti 1.0 \
    -r $ECEF \
    -o "$WORK/static.pos" \
    "$WORK/rover.26O" "$WORK/base_surveyed.26O" "$WORK/rover.26N" "$WORK/base.26N" >/dev/null 2>&1

if [ ! -s "$WORK/static.pos" ]; then
    echo "ERROR: static.pos пустой"; exit 1
fi

echo "[4/5] Проверка Q1"
Q1=$(awk '!/^%/{if($6==1) q++} END{print q+0}' "$WORK/static.pos")
N=$(grep -c '^20' "$WORK/static.pos")
echo "  Q1: $Q1 / $N"

if [ "$Q1" -lt 100 ]; then
    echo "  WARNING: мало Q1 (<100 эпох). Anchor может быть неточным."
fi

echo "[5/5] Усреднение anchor"
read -r LAT LON H N_EPOCH < <(LC_NUMERIC=C awk '!/^%/{n++; slat+=$3; slon+=$4; sh+=$5}
  END{printf "%.9f %.9f %.4f %d", slat/n, slon/n, sh/n, n}' "$WORK/static.pos")

echo
echo "════════════════════════════════════════"
echo "  ANCHOR (auto from progrev):"
echo "  $LAT $LON $H"
echo "  epochs used: $N_EPOCH"
echo "════════════════════════════════════════"
echo
echo "Сохранить в файл:"
echo "  echo \"$LAT $LON $H\" > $EXPERIMENT/conf/ANCHOR_<name>.txt"
