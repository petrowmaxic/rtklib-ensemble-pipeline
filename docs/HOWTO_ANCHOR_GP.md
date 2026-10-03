Anchor для gp (одиночный проект)

Как gp находит anchor

pipeline.sh определяет RUN_NAME = имя директории ровера. Ищет файл в conf/:

ANCHOR_<RUN_NAME>.txt — например ANCHOR_20260922_1.txt
ANCHOR_<YYYYMMDD>.txt — например ANCHOR_20260922.txt
ANCHOR_Julietta.txt — общий
Первый найденный используется. Если ни одного — pipeline работает с anchor = (0,0,0) (то есть без tie-breaker).

Что делает gp с anchor

ensemble_viterbi.py читает ANCHOR_LAT/ANCHOR_LON/ANCHOR_H из env. Pipeline экспортирует их из найденного файла.

В логе на шаге [4/5] Viterbi merge:

text
anchor: lat=61.161617224 lon=154.015110239 h=832.4633
Как получить anchor для gp-проекта

Автоматически (для первого вылета дня)

bash
# 1. Обработать проект
gp

# 2. Извлечь anchor
~/gnss_experiment/scripts/make_anchor_for_day.sh 20260922_1
# → ~/gnss_experiment/conf/ANCHOR_20260922.txt

# 3. Следующие gp-прогоны в тот же день используют ANCHOR_20260922.txt
Вручную

bash
python3 ~/gnss_experiment/scripts/detect_warmup.py \
    ~/gnss_pipeline_runs/20260922_1_<ts>/result.pos 0.5 300
# Сохранить строку ANCHOR:
Из отдельной статичной стоянки

См. HOWTO_ANCHOR.md раздел 4.

Работает без anchor

Pipeline использует ANCHOR_Julietta.txt или (0,0,0). На данных Julietta anchor не влияет на Q1 (см. REPORT.md 5.4.1). Влияние — на mean_dH в проблемных проектах.

Проверка

После gp в логе ищи:

text
[4/5] Viterbi merge
  anchor: lat=61.161617224 lon=154.015110239 h=832.4633
Если anchor: lat=0.000000000 — pipeline не нашёл anchor. Работает, но без tie-breaker.

Отладка

Симптом	Причина	Решение
ANCHOR_LAT / ANCHOR_LON / ANCHOR_H не заданы	Pipeline не экспортировал env	Проверить grep ANCHOR_FILE в pipeline.sh
Q1 = 0 %	Anchor с ошибкой + большой BONUS	Откатить, использовать ANCHOR_Julietta.txt
anchor: lat=0	Файл пустой	Пересоздать через make_anchor_for_day.sh