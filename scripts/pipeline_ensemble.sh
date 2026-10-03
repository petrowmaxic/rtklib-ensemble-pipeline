#!/usr/bin/env bash
# 8 прогонов (4 elmask × 2 soltype) для ensemble.
set -uo pipefail

ROVER="$1"; BASE_DIR="$2"; WORK="$3"

BIN="$HOME/gnss_experiment/bin/rnx2rtkp_EX"
CONF="$HOME/gnss_experiment/conf/FINAL.conf"
ECEF="${BASE_ECEF:--2772947.5700 1351588.2062 5564759.1253}"
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
N_JOBS=${N_JOBS:-6}

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
