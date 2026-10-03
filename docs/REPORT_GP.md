# gp — быстрая инструкция

## Запуск

gp

Интерактивный ввод:
1. Путь к .NOV ровера
2. Путь к .ubx базы (файл или директория)
3. ECEF базы (Enter = последнее значение)
4. Подтверждение [Y/n]

## Что делает

1. Слияние UBX (если >=2)
2. UBX -> RINEX базы
3. Патч APPROX POSITION
4. NOV -> RINEX ровера (NovAtel Convert)
5. 8 прогонов rnx2rtkp (N_JOBS=6, параллельно)
6. Viterbi merge
7. Экспорт XYZ + summary

## Результат

- rover_dir/<project>_<timestamp>.xyz - Oasis XYZ
- rover_dir/<project>_<timestamp>.txt - summary
- ~/gnss_pipeline_runs/<project>_<timestamp>/ - все промежуточные

## Время

- Первый прогон: ~10 мин
- Повторный: ~3 мин

## Требования

- conf/ANCHOR_<project>.txt или conf/ANCHOR_Julietta.txt
- CrossOver + NovAtel Convert
- RTKLIB-EX бинарники в ~/gnss_experiment/bin/

## Отладка

См. REPORT.md раздел 5.4 и APPENDIX_C_errors.md.
