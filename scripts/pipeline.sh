#!/usr/bin/env bash
# GNSS pipeline: NOV ровера + UBX базы -> XYZ для Oasis Montaj.
# База может быть указана как отдельный файл .ubx или как директория с *.ubx —
# в этом случае все файлы автоматически сливаются в один по хронологии.
#
# Защита от перезаписи:
#   - существующий merged.ubx в директории базы → merged_<timestamp>.ubx
#   - существующий <name>.xyz рядом с ровером  → <name>_<timestamp>.xyz
#
# usage:
#   pipeline.sh                                       # полностью интерактивно
#   pipeline.sh <rover.NOV> <base.ubx | base_dir>     # ECEF спросит
#   pipeline.sh <rover.NOV> <base> "X Y Z"            # неинтерактивно
set -uo pipefail

# ============ НАСТРОЙКИ ============
EXPERIMENT_DIR="$HOME/gnss_experiment"
BIN_CONVBIN="$EXPERIMENT_DIR/bin/convbin_EX"
BIN_RNX2RTKP="$EXPERIMENT_DIR/bin/rnx2rtkp_EX"
CONF="$EXPERIMENT_DIR/conf/FINAL.conf"
EXPORT_SCRIPT="$EXPERIMENT_DIR/scripts/export_v2.py"
PATCH_SCRIPT="$EXPERIMENT_DIR/scripts/patch_approx_position.py"
MERGE_SCRIPT="$EXPERIMENT_DIR/scripts/merge_ubx.py"
DOP_CHECK_SCRIPT="$EXPERIMENT_DIR/scripts/check_dop_100s.py"
GAPS_CHECK_SCRIPT="$EXPERIMENT_DIR/scripts/check_time_gaps.py"
RUNS_DIR="$HOME/gnss_pipeline_runs"
ECEF_CACHE="$HOME/.gnss_pipeline_last_ecef"

CROSSOVER_WINE="/Applications/CrossOver.app/Contents/SharedSupport/CrossOver/CrossOver-Hosted Application/wine"
NOVATEL_EXE="/Users/maxic/Library/Application Support/CrossOver/Bottles/Novatel converter/drive_c/Program Files/NovAtel Convert/NovAtelConvert.exe"

# ============ ИНФРАСТРУКТУРА ============
check_infrastructure() {
    local ok=1
    [ -x "$BIN_CONVBIN" ]   || { echo "ERROR: не найден $BIN_CONVBIN";   ok=0; }
    [ -x "$BIN_RNX2RTKP" ]  || { echo "ERROR: не найден $BIN_RNX2RTKP";  ok=0; }
    [ -f "$CONF" ]          || { echo "ERROR: не найден $CONF";          ok=0; }
    [ -f "$EXPORT_SCRIPT" ] || { echo "ERROR: не найден $EXPORT_SCRIPT"; ok=0; }
    [ -f "$PATCH_SCRIPT" ]  || { echo "ERROR: не найден $PATCH_SCRIPT";  ok=0; }
    [ -f "$MERGE_SCRIPT" ]  || { echo "ERROR: не найден $MERGE_SCRIPT";  ok=0; }
    [ -f "$DOP_CHECK_SCRIPT" ] || { echo "ERROR: не найден $DOP_CHECK_SCRIPT"; ok=0; }
    [ -f "$GAPS_CHECK_SCRIPT" ] || { echo "ERROR: не найден $GAPS_CHECK_SCRIPT"; ok=0; }
    [ -x "$CROSSOVER_WINE" ]|| { echo "ERROR: CrossOver не найден";      ok=0; }
    [ -f "$NOVATEL_EXE" ]   || { echo "ERROR: NovAtel Convert не найден"; ok=0; }
    [ $ok -eq 1 ] || exit 1
}

# ============ ИНТЕРАКТИВНЫЕ ЗАПРОСЫ ============
ask_file() {
    local prompt="$1"
    local result=""
    while true; do
        printf "  %s\n  > " "$prompt" >&2
        read -r result
        result="${result/#\~/$HOME}"
        if [ -f "$result" ]; then
            echo "$result"; return 0
        fi
        printf "  ⚠ Файл не найден: %s\n  Попробуйте ещё раз (Ctrl+C — отмена)\n" "$result" >&2
    done
}

ask_base() {
    local prompt="$1"
    local default="${2:-}"
    local result=""
    while true; do
        if [ -n "$default" ]; then
            printf "  %s\n  [Enter — %s]\n  > " "$prompt" "$default" >&2
        else
            printf "  %s\n  > " "$prompt" >&2
        fi
        read -r result
        result="${result/#\~/$HOME}"
        if [ -z "$result" ] && [ -n "$default" ]; then
            result="$default"
        fi
        if [ -f "$result" ]; then
            echo "$result"; return 0
        fi
        if [ -d "$result" ]; then
            local cnt
            cnt=$(find "$result" -maxdepth 1 -name '*.ubx' -type f | wc -l | tr -d ' ')
            if [ "$cnt" -gt 0 ]; then
                echo "$result"; return 0
            fi
            printf "  ⚠ В директории нет *.ubx: %s\n  Попробуйте ещё раз (Ctrl+C — отмена)\n" "$result" >&2
            continue
        fi
        printf "  ⚠ Не найдено: %s\n  Попробуйте ещё раз (Ctrl+C — отмена)\n" "$result" >&2
    done
}

ask_ecef() {
    local default="$1"
    local result=""
    printf "  Координаты базы (ECEF X Y Z, метры)\n" >&2
    if [ -n "$default" ]; then
        printf "  последнее значение: %s\n  [Enter — использовать последнее]\n  > " "$default" >&2
    else
        printf "  [например: -2772947.5700 1351588.2062 5564759.1253]\n  > " >&2
    fi
    read -r result
    if [ -z "$result" ] && [ -n "$default" ]; then
        result="$default"
    fi
    local a b c extra
    read -r a b c extra <<< "$result"
    if [ -z "$a" ] || [ -z "$b" ] || [ -z "$c" ] || [ -n "$extra" ]; then
        printf "  ⚠ Ожидалось ровно три числа\n" >&2
        return 1
    fi
    for v in "$a" "$b" "$c"; do
        if ! echo "$v" | grep -qE '^-?[0-9]+(\.[0-9]+)?$'; then
            printf "  ⚠ Не число: %s\n" "$v" >&2
            return 1
        fi
    done
    echo "$result"
    return 0
}

ask_confirm() {
    local ans
    printf "  %s [Y/n] > " "$1" >&2
    read -r ans
    case "$ans" in
        [nN]*) return 1 ;;
        *) return 0 ;;
    esac
}

# ============ MAIN ============
check_infrastructure

echo "════════════════════════════════════════════════════"
echo "  GNSS pipeline"
echo "════════════════════════════════════════════════════"
echo

ARG_ROVER="${1:-}"
ARG_BASE="${2:-}"
ARG_ECEF="${3:-}"

# --- Ровер ---
echo "[1/3] Файл ровера (.NOV)"
if [ -n "$ARG_ROVER" ]; then
    [ -f "$ARG_ROVER" ] || { echo "  ⚠ Не найден: $ARG_ROVER"; exit 1; }
    ROVER_ABS=$(cd "$(dirname "$ARG_ROVER")" && pwd)/$(basename "$ARG_ROVER")
    echo "  $ROVER_ABS"
else
    ROVER_ABS=$(ask_file "Укажите путь к файлу ровера (.NOV):")
fi

# v1.4.6: .NOV extension check
case "$ROVER_ABS" in
    *.NOV|*.nov) : ;;
    *)
        echo "  ⚠ Файл не .NOV: $(basename "$ROVER_ABS")"
        echo "  NovAtel Convert читает только .NOV."
        printf "  Продолжить всё равно? [y/N] > "
        read -r _nov_ans
        case "$_nov_ans" in
            [yY]*) : ;;
            *) echo "  Отменено."; exit 1 ;;
        esac
        ;;
esac

# v1.4.3: gnss_meta resolve
GNSS_META="$EXPERIMENT_DIR/scripts/gnss_meta.py"
if [ -f "$GNSS_META" ]; then
    META_OUT=$(python3 "$GNSS_META" resolve "$ROVER_ABS" 2>/dev/null)
    if [ -n "$META_OUT" ]; then
        eval "$META_OUT"
    fi
fi
echo

# --- База ---
echo "[2/3] База (.ubx-файл или директория с *.ubx)"
if [ -n "$ARG_BASE" ]; then
    if [ -f "$ARG_BASE" ]; then
        BASE_ABS=$(cd "$(dirname "$ARG_BASE")" && pwd)/$(basename "$ARG_BASE")
    elif [ -d "$ARG_BASE" ]; then
        BASE_ABS=$(cd "$ARG_BASE" && pwd)
    else
        echo "  ⚠ Не найдено: $ARG_BASE"; exit 1
    fi
    echo "  $BASE_ABS"
else
    BASE_ABS=$(ask_base "Укажите .ubx или директорию с .ubx:" "${GNSS_BASE_DIR:-}")
fi

UBX_LIST=()
if [ -d "$BASE_ABS" ]; then
    if [ -f "$BASE_ABS/merged.ubx" ]; then
        echo "  найден merged.ubx — использую его (слияние пропущено)"
        UBX_LIST=("$BASE_ABS/merged.ubx")
    else
        while IFS= read -r f; do
            UBX_LIST+=("$f")
        done < <(find "$BASE_ABS" -maxdepth 1 -name '*.ubx' -type f \
                    ! -name 'merged.ubx' ! -name 'merged_*.ubx' | sort)
    fi
    if [ ${#UBX_LIST[@]} -eq 0 ]; then
        echo "  ⚠ В директории нет *.ubx"; exit 1
    fi
    if [ ${#UBX_LIST[@]} -eq 1 ]; then
        echo "  найден 1 файл: $(basename "${UBX_LIST[0]}")"
    else
        echo "  найдено ${#UBX_LIST[@]} файла — будут слиты по хронологии:"
        for f in "${UBX_LIST[@]}"; do
            echo "    • $(basename "$f")"
        done
    fi
else
    UBX_LIST=("$BASE_ABS")
fi
echo

# --- ECEF ---
echo "[3/3] Координаты базы (ECEF)"
LAST_ECEF=""
if [ -f "$ECEF_CACHE" ]; then
    LAST_ECEF=$(cat "$ECEF_CACHE" | tr -d '\n')
fi
if [ -n "$ARG_ECEF" ]; then
    ECEF="$ARG_ECEF"
    echo "  $ECEF"
else
    ECEF=""
    if [ -n "${GNSS_ROVER_NOV:-}" ] && [ -f "$GNSS_META" ]; then
        ECEF=$(python3 "$GNSS_META" read-base "$GNSS_ROVER_NOV" 2>/dev/null | head -1)
        [ -n "$ECEF" ] && echo "  $ECEF  (gnss_meta)"
    fi
    if [ -z "$ECEF" ]; then
        while ! ECEF=$(ask_ecef "$LAST_ECEF"); do
            echo "  Повторите ввод."
        done
    fi
fi
echo

# --- Производные пути ---
ROVER_DIR=$(dirname "$ROVER_ABS")
RUN_NAME=$(basename "$ROVER_DIR")
TIMESTAMP=$(date +%H%M%S)_$$
WORK_DIR="$RUNS_DIR/${RUN_NAME}_${TIMESTAMP}"

# --- Защита от перезаписи выходного .xyz ---
OUTPUT_XYZ="$ROVER_DIR/${RUN_NAME}.xyz"
OUTPUT_XYZ_NOTE=""
if [ -f "$OUTPUT_XYZ" ]; then
    OUTPUT_XYZ="$ROVER_DIR/${RUN_NAME}_${TIMESTAMP}.xyz"
    OUTPUT_XYZ_NOTE="⚠ ${RUN_NAME}.xyz существует → $(basename "$OUTPUT_XYZ")"
fi

# --- Защита от перезаписи merged.ubx ---
MERGED_PATH=""
MERGED_NOTE=""
if [ ${#UBX_LIST[@]} -gt 1 ]; then
    if [ -d "$BASE_ABS" ]; then
        # сохраняем merged в директории базы (переиспользуемо)
        MERGED_PATH="$BASE_ABS/merged.ubx"
        if [ -f "$MERGED_PATH" ]; then
            MERGED_PATH="$BASE_ABS/merged_${TIMESTAMP}.ubx"
            MERGED_NOTE="⚠ merged.ubx существует → $(basename "$MERGED_PATH")"
        fi
    else
        # база — один файл, но их несколько? сохраняем в work_dir
        MERGED_PATH="$WORK_DIR/base_merged.ubx"
    fi
fi

# --- Сводка ---
echo "════════════════════════════════════════════════════"
echo "  Параметры запуска"
echo "────────────────────────────────────────────────────"
echo "  ровер:   $ROVER_ABS"
echo "  база:    $BASE_ABS"
if [ ${#UBX_LIST[@]} -gt 1 ]; then
    echo "  ubx:     ${#UBX_LIST[@]} файлов → слияние"
    echo "  merged:  $MERGED_PATH"
elif [ ${#UBX_LIST[@]} -eq 1 ]; then
    echo "  ubx:     $(basename "${UBX_LIST[0]}")"
fi
echo "  ECEF:    $ECEF"
echo "  output:  $OUTPUT_XYZ"
echo "  work:    $WORK_DIR"
if [ -n "$OUTPUT_XYZ_NOTE" ]; then
    echo
    echo "  $OUTPUT_XYZ_NOTE"
fi
if [ -n "$MERGED_NOTE" ]; then
    echo "  $MERGED_NOTE"
fi
echo "════════════════════════════════════════════════════"
echo

if ! ask_confirm "Запустить обработку?"; then
    echo "Отменено."
    exit 0
fi
echo

echo "$ECEF" > "$ECEF_CACHE"
mkdir -p "$WORK_DIR/logs"
START_TIME=$(date +%s)

# ============ ШАГ 0: СЛИЯНИЕ UBX ============
if [ ${#UBX_LIST[@]} -gt 1 ]; then
    echo "[0/5] Слияние ${#UBX_LIST[@]} UBX файлов"
    python3 "$MERGE_SCRIPT" "$MERGED_PATH" "${UBX_LIST[@]}" \
        > "$WORK_DIR/logs/merge_ubx.log" 2>&1
    if [ ! -f "$MERGED_PATH" ]; then
        echo "  ✗ Слияние не удалось"
        cat "$WORK_DIR/logs/merge_ubx.log"
        exit 1
    fi
    BASE_UBX="$MERGED_PATH"
    echo "  ✓ $(basename "$MERGED_PATH") ($(wc -c < "$BASE_UBX" | tr -d ' ') байт)"
else
    BASE_UBX="${UBX_LIST[0]}"
fi

# ============ ШАГ 1: БАЗА ============
echo "[1/5] База: UBX → RINEX"
"$BIN_CONVBIN" -r ubx -o "$WORK_DIR/base.26O" -n "$WORK_DIR/base.26N" "$BASE_UBX" \
    > "$WORK_DIR/logs/base_convbin.log" 2>&1
if [ ! -f "$WORK_DIR/base.26O" ]; then
    echo "  ✗ Ошибка: не создан base.26O"
    tail -20 "$WORK_DIR/logs/base_convbin.log"
    exit 1
fi
echo "  ✓ base.26O ($(wc -c < "$WORK_DIR/base.26O" | tr -d ' ') байт)"

# ============ ШАГ 2: ПАТЧ ============
echo "[2/5] Патч APPROX POSITION базы"
python3 "$PATCH_SCRIPT" "$WORK_DIR/base.26O" $ECEF > "$WORK_DIR/logs/patch_base.log" 2>&1
if [ $? -ne 0 ]; then
    echo "  ✗ Патч не удался"
    cat "$WORK_DIR/logs/patch_base.log"
    exit 1
fi
cp "$WORK_DIR/base.26O" "$WORK_DIR/base_surveyed.26O"
echo "  ✓ OK"

# ============ ШАГ 3: РОВЕР ============
echo "[3/5] Ровер: NOV → RINEX (NovAtel Convert через CrossOver)"
cp "$ROVER_ABS" "$WORK_DIR/rover.NOV"
cd "$WORK_DIR"
"$CROSSOVER_WINE" "$NOVATEL_EXE" -r3.03 rover.NOV \
    > "$WORK_DIR/logs/rover_novatel.log" 2>&1
NV_OBS=$(find "$WORK_DIR" -maxdepth 1 -name 'rover.[0-9][0-9]O' -type f | head -1)
NV_NAV=$(find "$WORK_DIR" -maxdepth 1 -name 'rover.[0-9][0-9]N' -type f | head -1)

if [ -z "$NV_OBS" ] || [ -z "$NV_NAV" ]; then
    echo "  ✗ NovAtel Convert не создал rover.<NN>O / .<NN>N"
    echo "  Содержимое WORK_DIR:"
    ls -la "$WORK_DIR" | head -20
    echo "  Хвост лога:"
    tail -30 "$WORK_DIR/logs/rover_novatel.log"
    exit 1
fi

if [ "$(basename "$NV_OBS")" != "rover.26O" ]; then
    echo "  ⚠ NovAtel создал $(basename "$NV_OBS") / $(basename "$NV_NAV") — нормализую в rover.26O/.26N"
fi
mv "$NV_OBS" "$WORK_DIR/rover.26O"
mv "$NV_NAV" "$WORK_DIR/rover.26N"
ROVER_SIZE=$(wc -c < "$WORK_DIR/rover.26O" | tr -d ' ')
echo "  ✓ rover.26O ($ROVER_SIZE байт)"
if [ "$ROVER_SIZE" -lt 1000000 ]; then
    echo "  ✗ rover.26O слишком мал ($ROVER_SIZE байт, минимум 1 МБ)"
    echo "  Возможно, NovAtel Convert был прерван."
    exit 1
fi

# ============ ШАГ 3.6: AUTO-ANCHOR для первого вылета дня ============
ANCHOR_DATE="${RUN_NAME:0:8}"
# AUTO-ANCHOR отключён: перенесён в отдельный скрипт make_anchor_for_day.sh
if false; then
    ANCHOR_DAY_FILE="$EXPERIMENT_DIR/conf/ANCHOR_${ANCHOR_DATE}.txt"
    if [ ! -f "$ANCHOR_DAY_FILE" ]; then
        echo "[3.6/5] Auto-anchor для ${RUN_NAME} (прогрев ровера)"
        ANCHOR_LINE=$(python3 "$EXPERIMENT_DIR/scripts/detect_warmup.py" \
    "$WORK_DIR/result.pos" 0.5 300 2>/dev/null | \
    grep "^ANCHOR:" | awk '{print $2, $3, $4}')
        if [ -n "$ANCHOR_LINE" ]; then
            echo "$ANCHOR_LINE" > "$ANCHOR_DAY_FILE"
            echo "  ✓ anchor: $ANCHOR_LINE → conf/ANCHOR_${ANCHOR_DATE}.txt"
        else
            echo "  ⚠ auto-anchor не удался, fallback на ANCHOR_Julietta.txt"
        fi
    else
        echo "  ✓ anchor дня уже есть: ANCHOR_${ANCHOR_DATE}.txt"
    fi
fi

# ============ ШАГ 3.5: ENSEMBLE С СЕГМЕНТАЦИЕЙ ============
echo "[3.5/5] Ensemble с сегментацией (v1.4.3)"

export N_JOBS="${N_JOBS:-6}"
export BASE_ECEF="$ECEF"

# v1.4.3: сначала gnss_meta.read-anchor (priority: day -> area -> legacy)
ANCHOR_DATE="${RUN_NAME:0:8}"
ANCHOR_LINE=""
if [ -n "${GNSS_ROVER_NOV:-}" ] && [ -f "$GNSS_META" ]; then
    ANCHOR_LINE=$(python3 "$GNSS_META" read-anchor "$GNSS_ROVER_NOV" 2>/dev/null | head -1)
fi

if [ -n "$ANCHOR_LINE" ]; then
    read -r ANCHOR_LAT ANCHOR_LON ANCHOR_H <<< "$ANCHOR_LINE"
    export ANCHOR_LAT ANCHOR_LON ANCHOR_H
    echo "  anchor (gnss_meta): lat=$ANCHOR_LAT lon=$ANCHOR_LON h=$ANCHOR_H"
else
    ANCHOR_FILE=""
    if [ -f "$EXPERIMENT_DIR/conf/ANCHOR_${RUN_NAME}.txt" ]; then
        ANCHOR_FILE="$EXPERIMENT_DIR/conf/ANCHOR_${RUN_NAME}.txt"
    elif [ -f "$EXPERIMENT_DIR/conf/ANCHOR_${ANCHOR_DATE}.txt" ]; then
        ANCHOR_FILE="$EXPERIMENT_DIR/conf/ANCHOR_${ANCHOR_DATE}.txt"
    elif [ -f "$EXPERIMENT_DIR/conf/ANCHOR_Julietta.txt" ]; then
        ANCHOR_FILE="$EXPERIMENT_DIR/conf/ANCHOR_Julietta.txt"
    fi

    if [ -z "$ANCHOR_FILE" ]; then
        echo "  WARN: нет anchor"
        exit 1
    fi

    read -r ANCHOR_LAT ANCHOR_LON ANCHOR_H < "$ANCHOR_FILE"
    export ANCHOR_LAT ANCHOR_LON ANCHOR_H
    echo "  anchor (legacy): lat=$ANCHOR_LAT lon=$ANCHOR_LON h=$ANCHOR_H"
fi

python3 "$EXPERIMENT_DIR/scripts/ensemble_segmented.py" "$WORK_DIR" \
    > "$WORK_DIR/logs/ensemble_segmented.log" 2>&1 || {
    echo "  ✗ ensemble_segmented.py упал"
    tail -40 "$WORK_DIR/logs/ensemble_segmented.log"
    exit 1
}

grep -E "^  Сегмент|^  Склейка|^  Итого" "$WORK_DIR/logs/ensemble_segmented.log" \
    | sed 's/^/  /'

if [ ! -f "$WORK_DIR/result.pos" ]; then
    echo "  ✗ result.pos не создан"
    exit 1
fi

N_EPOCH=$(grep -c '^20' "$WORK_DIR/result.pos")
echo "  ✓ result.pos ($N_EPOCH эпох)"

# Симлинк для .stat — экспорт требует его
if [ ! -f "$WORK_DIR/result.pos.stat" ]; then
    BACKWARD_STAT="$WORK_DIR/ensemble/e15_backward.pos.stat"
    [ -f "$BACKWARD_STAT" ] && ln -sf "ensemble/e15_backward.pos.stat" "$WORK_DIR/result.pos.stat" \
        && echo "  ✓ result.pos.stat → ensemble/e15_backward.pos.stat"
fi

# ============ ШАГ 5: ЭКСПОРТ ============
echo "[5/5] Экспорт в XYZ"
python3 "$EXPORT_SCRIPT" "$WORK_DIR/result.pos" "$WORK_DIR/result.pos.stat" "$OUTPUT_XYZ" \
    > "$WORK_DIR/logs/export.log" 2>&1
if [ ! -f "$OUTPUT_XYZ" ]; then
    echo "  ✗ Экспорт не удался"
    cat "$WORK_DIR/logs/export.log"
    exit 1
fi
N_OUT=$(wc -l < "$OUTPUT_XYZ" | tr -d ' ')
echo "  ✓ $N_OUT строк"

# Генерируем статистику в стиле GrafNav
SUMMARY_TXT="${OUTPUT_XYZ%.xyz}.txt"
python3 "$EXPERIMENT_DIR/scripts/generate_summary.py" \
    "$WORK_DIR/result.pos" "$SUMMARY_TXT" \
    --baseline-base-ecef $ECEF >/dev/null 2>&1
if [ -f "$SUMMARY_TXT" ]; then
    echo "  ✓ статистика: $(basename "$SUMMARY_TXT")"
fi

END_TIME=$(date +%s)
ELAPSED=$((END_TIME - START_TIME))

echo
echo "════════════════════════════════════════════════════"
echo "  ГОТОВО за ${ELAPSED} сек"
echo "────────────────────────────────────────────────────"
echo "  Файл:  $OUTPUT_XYZ"
echo "  Стат:  ${OUTPUT_XYZ%.xyz}.txt"
echo "  Эпох:  $N_EPOCH"
echo "  Логи:  $WORK_DIR/logs/"
if [ ${#UBX_LIST[@]} -gt 1 ]; then
    echo "  Merged: $MERGED_PATH"
fi
echo "════════════════════════════════════════════════════"

# ============ СТАТИСТИКА И ПРОВЕРКА ТЗ ============
echo
echo "════════════════════════════════════════════════════"
echo "  СТАТИСТИКА"
echo "════════════════════════════════════════════════════"
echo

echo "  Q-распределение (result.pos):"
awk -v total="$N_EPOCH" '!/^%/{q[$6]++} END{
    for(k in q) printf "    Q=%s: %6d  (%5.2f%%)\n", k, q[k], 100*q[k]/total
}' "$WORK_DIR/result.pos" | sort -t= -k2 -n

Q1_CNT=$(awk '!/^%/{q[$6]++} END{print q[1]+0}' "$WORK_DIR/result.pos")
Q1_PCT=$(awk -v q1="$Q1_CNT" -v n="$N_EPOCH" 'BEGIN{printf "%.2f", 100*q1/n}')
echo "    → Q1 (fix): $Q1_CNT / $N_EPOCH = ${Q1_PCT}%"
echo

echo "  Проверка ТЗ (DOP > 10 непрерывно ≤ 100 с):"
DOP_OUT=$(python3 "$DOP_CHECK_SCRIPT" "$OUTPUT_XYZ" 10.0 2>&1)
echo "$DOP_OUT" | grep -E "^--- |интервалов выше|самый длинный|✅|❌" | sed 's/^/    /'

if echo "$DOP_OUT" | grep -q "❌"; then
    echo "    ⚠ ТЗ НАРУШЕНО"
else
    echo "    ✓ ТЗ по DOP ВЫПОЛНЕНО"
fi
echo

echo "  Временные пропуски:"
GAPS_OUT=$(python3 "$GAPS_CHECK_SCRIPT" "$OUTPUT_XYZ" 2>&1)
echo "$GAPS_OUT" | grep -E "эпох в файле|пропущено эпох|интервалов >" | sed 's/^/    /'
echo
