#!/usr/bin/env bash
# Батч: для каждого проекта — pipeline quiet (8 прогонов) + Viterbi + summary.
set -uo pipefail

ROVER_ROOT="/Users/maxic/Documents/1_Data.nosync/Julietta"
BASE_ROOT="/Users/maxic/Documents/2_Diff.nosync/Julietta"
WORK_ROOT="$HOME/gnss_batch_runs"
CSV="$WORK_ROOT/batch_results.csv"
# ANCHOR: приоритет project > day > Julietta
# ANCHOR_FILE устанавливается в цикле по каждому проекту
ANCHOR_FILE=""

mkdir -p "$WORK_ROOT"

# ANCHOR_FILE на старте пуст — читаем только если он реально задан
if [ -n "${ANCHOR_FILE:-}" ] && [ -f "$ANCHOR_FILE" ]; then
    read -r ANCHOR_LAT ANCHOR_LON ANCHOR_H < "$ANCHOR_FILE"
    export ANCHOR_LAT ANCHOR_LON ANCHOR_H
fi
# C1: ECEF базы (можно переопределить через env)
export BASE_ECEF="${BASE_ECEF:--2772947.5700 1351588.2062 5564759.1253}"
# N_JOBS default 6; override: N_JOBS=8 bash batch_ensemble.sh
export N_JOBS="${N_JOBS:-6}"

# PROJECTS_OVERRIDE — для тестового запуска на подмножестве
# Usage: PROJECTS_OVERRIDE="20260918_2 20260901_1" bash batch_ensemble.sh
if [ -n "${PROJECTS_OVERRIDE:-}" ]; then
    PROJECTS=(${PROJECTS_OVERRIDE})
else
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
fi

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

    # v1.3.1: конвертация только если нужно (rover.26O/base_surveyed.26O отсутствуют)
    mkdir -p "$WORK"
    if [ ! -s "$WORK/rover.26O" ] || [ ! -s "$WORK/base_surveyed.26O" ]; then
        "$HOME/gnss_experiment/scripts/pipeline_ensemble.sh" "$ROVER_NOV" "$BASE_DIR" "$WORK" >/dev/null 2>&1 || {
            echo "$PROJ,,,,,,,fail_pipeline" >> "$CSV"
            continue
        }
    fi

    # 2. Viterbi
    VIT="$WORK/ensemble_viterbi.pos"

    # v1.3.1: N_POS проверка убрана (ensemble/ больше не создаётся — segmentation)

    # Удалить старые .pos/.stat (для чистого перезаписи)
    [ -f "$VIT" ] && rm -f "$VIT"
    [ -f "$WORK/result.pos" ] && rm -f "$WORK/result.pos"
    [ -f "$WORK/result.pos.stat" ] && rm -f "$WORK/result.pos.stat"
    [ -f "$WORK/ensemble_viterbi.pos.stat" ] && rm -f "$WORK/ensemble_viterbi.pos.stat"
    # --- AUTO-ANCHOR из первых эпох (если нет ANCHOR дня) ---
    # --- ВЫБОР ANCHOR для проекта ---
    ANCHOR_DATE="${PROJ:0:8}"
    if [ -f "$HOME/gnss_experiment/conf/ANCHOR_${PROJ}.txt" ]; then
        PROJ_ANCHOR="$HOME/gnss_experiment/conf/ANCHOR_${PROJ}.txt"
        echo "  anchor: project-specific (${PROJ})"
    elif [ -f "$HOME/gnss_experiment/conf/ANCHOR_${ANCHOR_DATE}.txt" ]; then
        PROJ_ANCHOR="$HOME/gnss_experiment/conf/ANCHOR_${ANCHOR_DATE}.txt"
        echo "  anchor: day-level (${ANCHOR_DATE})"
    else
        PROJ_ANCHOR="$HOME/gnss_experiment/conf/ANCHOR_Julietta.txt"
        echo "  anchor: Julietta-level (общий)"
    fi
    ANCHOR_LAT="${ANCHOR_LAT:-61.161609573}"
    ANCHOR_LON="${ANCHOR_LON:-154.015098774}"
    ANCHOR_H="${ANCHOR_H:-832.4611}"
    export ANCHOR_LAT ANCHOR_LON ANCHOR_H
    if [ -f "$PROJ_ANCHOR" ]; then
        read -r ANCHOR_LAT ANCHOR_LON ANCHOR_H < "$PROJ_ANCHOR"
        echo "    lat=$ANCHOR_LAT lon=$ANCHOR_LON h=$ANCHOR_H"
    fi

    # v1.4.6: блок auto-day-anchor удалён (не работает с v1.3.0+)

    # v1.3.0: сегментная обработка вместо монолитного Viterbi
    export N_JOBS="${N_JOBS:-6}"
    export BASE_ECEF="${BASE_ECEF:--2772947.5700 1351588.2062 5564759.1253}"
    python3 "$HOME/gnss_experiment/scripts/ensemble_segmented.py" "$WORK" \
        2>&1 | tee -a "$WORK/logs/ensemble_segmented.log"
    if [ -f "$WORK/result.pos" ]; then
        mv "$WORK/result.pos" "$VIT"
        # .stat идёт рядом с result.pos
        if [ -f "$WORK/result.pos.stat" ]; then
            rm -f "$WORK/ensemble_viterbi.pos.stat"
            mv "$WORK/result.pos.stat" "$WORK/ensemble_viterbi.pos.stat"
        fi
    fi

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
