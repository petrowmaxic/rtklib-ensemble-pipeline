#!/usr/bin/env bash
# Извлечь anchor из PROJECT_1 (первого вылета дня) и сохранить ANCHOR_<date>.txt.
# usage: make_anchor_for_day.sh <project_1_name>
set -uo pipefail

PROJ="${1:-}"
[ -z "$PROJ" ] && { echo "usage: $0 <project_1_name>"; exit 1; }

EXPERIMENT="$HOME/gnss_experiment"
BATCH="$HOME/gnss_batch_runs/$PROJ"

if [ ! -d "$BATCH" ]; then
    echo "ERROR: нет $BATCH"; exit 1
fi

POS="$BATCH/ensemble_viterbi.pos"
[ ! -f "$POS" ] && POS="$BATCH/result.pos"
[ ! -f "$POS" ] && { echo "ERROR: нет .pos в $BATCH"; exit 1; }

DATE="${PROJ:0:8}"
OUT="$EXPERIMENT/conf/ANCHOR_${DATE}.txt"

echo "Анализ $POS (статика ≥300 с, v < 0.5 м/с)..."
LINE=$(python3 "$EXPERIMENT/scripts/detect_warmup.py" "$POS" 0.5 300 2>/dev/null | \
       grep '^ANCHOR:' | awk '{print $2, $3, $4}')

if [ -z "$LINE" ]; then
    echo "⚠ статика не найдена в $PROJ. Anchor не сохранён."
    echo "  Используйте существующий ANCHOR_Julietta.txt"
    exit 1
fi

echo "$LINE" > "$OUT"
echo "✓ $OUT"
echo "  $LINE"
