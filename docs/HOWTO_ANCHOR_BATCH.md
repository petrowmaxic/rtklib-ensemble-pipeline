Anchor для batch_ensemble.sh

Как batch находит anchor

batch_ensemble.sh в цикле по проектам вызывает логику выбора anchor для каждого проекта:

conf/ANCHOR_<project>.txt — например ANCHOR_20260922_1.txt
conf/ANCHOR_<YYYYMMDD>.txt — например ANCHOR_20260922.txt
conf/ANCHOR_Julietta.txt — общий
Первый найденный используется. Если ни одного — anchor = (0,0,0).

В логе:

text
  anchor: project-specific (20260922_1)
    lat=61.161617224 lon=154.015110239 h=832.4633
Подготовка перед batch

bash
# 1. Обработать первый вылет дня
~/gnss_experiment/scripts/batch_ensemble.sh

# 2. Создать ANCHOR_<date>.txt для каждого _1
for p in 20260818_1 20260819_1 20260821_1 20260826_1 20260831_1 \
         20260901_1 20260906_1 20260914_1 20260917_1 20260918_1 \
         20260921_1 20260922_1 20260920; do
    ~/gnss_experiment/scripts/make_anchor_for_day.sh "$p"
done

# 3. Повторный batch — использует day-level anchor для _2, _3...
~/gnss_experiment/scripts/batch_ensemble.sh
Что произойдёт при повторном batch

_1 и YYYYMMDD → ANCHOR_<date>.txt
_2, _3... → ANCHOR_<date>.txt того же дня
Без совпадений → ANCHOR_Julietta.txt
Ускорение: anchors до batch

Если заранее знаешь даты, создай anchors после первого batch:

bash
# 1. Первый batch — для _1 создадутся ensemble_viterbi.pos
~/gnss_experiment/scripts/batch_ensemble.sh

# 2. Извлечь anchors для всех _1 и YYYYMMDD
for p in $(ls ~/gnss_batch_runs/ | grep -E '_1$|^[0-9]{8}$'); do
    ~/gnss_experiment/scripts/make_anchor_for_day.sh "$p"
done

# 3. Второй batch — все проекты используют day-level
~/gnss_experiment/scripts/batch_ensemble.sh
Обновление anchors при новых данных

bash
# После первого batch
~/gnss_experiment/scripts/make_anchor_for_day.sh 20260925_1
# Следующий batch подхватит ANCHOR_20260925.txt
Резерв — ANCHOR_Julietta.txt

Fallback, если нет day-level. Используется для всех проектов без своего anchor. Обновляется вручную из надёжной статики.

Проверка приоритета (симуляция логики)

bash
RUN_NAME="20260921_2"
ANCHOR_DATE="${RUN_NAME:0:8}"

if [ -f "$HOME/gnss_experiment/conf/ANCHOR_${RUN_NAME}.txt" ]; then
    echo "  → project-specific"
elif [ -f "$HOME/gnss_experiment/conf/ANCHOR_${ANCHOR_DATE}.txt" ]; then
    echo "  → day-level: ANCHOR_${ANCHOR_DATE}.txt"
else
    echo "  → Julietta-level (fallback)"
fi
Ожидаем для 20260921_2: day-level: ANCHOR_20260921.txt.

Отладка

Симптом	Причина	Решение
anchor: Julietta-level для _2	Нет ANCHOR_<date>.txt	Запустить make_anchor_for_day.sh для _1
Q1 упал на проекте	Anchor проекта сдвинут >100 м	Сравнить с соседними anchors
~ не разворачивается	[ -f "~/..." ]	Использовать $HOME/...
Batch работает без anchors

Если anchors нет — все проекты используют ANCHOR_Julietta.txt или работают без anchor. Q1 не падает (проверено на 42 проектах). Anchors — оптимизация качества.