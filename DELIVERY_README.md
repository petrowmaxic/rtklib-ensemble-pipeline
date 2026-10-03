# GNSS Julietta Pipeline — комплект для развёртывания

## Что это

Открытый пайплайн GNSS-постобработки на RTKLIB-EX 2.5.1.
Заменяет GrafNav 8.70.5101. Средний Q1 = 92.6% на 41 проекте Julietta.

## Быстрый старт

1. Распаковать в ~/gnss_experiment/
2. Заменить "maxic" на своё имя: см. docs/REPORT.md раздел 6
3. chmod +x на bin/* и scripts/*
4. Прочитать docs/REPORT_GP.md
5. Первый прогон: gp на 20260922_1 (ожидаемый Q1 = 88.88%)

## Что читать

- docs/REPORT.md — полный отчёт
- docs/REPORT_GP.md — как запускать
- docs/HOWTO_ANCHOR.md — anchor (общее)
- docs/HOWTO_ANCHOR_GP.md — anchor для gp
- docs/HOWTO_ANCHOR_BATCH.md — anchor для batch
- docs/APPENDIX_C_errors.md — грабли
- docs/PROTOCOLS.md — протоколы измерений
- docs/JOURNAL.md — полная история

## Исходные данные (НЕ включены)

- ~/Documents/1_Data.nosync/Julietta/<project>/<project>.NOV
- ~/Documents/2_Diff.nosync/Julietta/<YYYYMMDD>/gnss_*.ubx

Передаются отдельно.

## Контрольная точка развёртывания

gp на 20260922_1 → Q1 = 88.88%, mean = −11 см.
Если совпадает — пайплайн готов.
