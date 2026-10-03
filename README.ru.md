[English](README.md) | [Русский](README.ru.md)

# RTKLIB Ensemble Pipeline

Пайплайн GNSS-постобработки для вертолётной аэросъёмки. Открытая замена
GrafNav, построен на [RTKLIB-EX 2.5.1 (demo5)](https://github.com/rtklibexplorer/RTKLIB).

Объединяет **8 параллельных прогонов RTKLIB** (elmask x направление)
через **Viterbi-ансамбль**, с **автоматическим разделением трека на
вылеты** и **метаданными рядом с исходными данными** (anchor, координаты
базы).

## Ключевые особенности

- **Сегментная обработка.** Автоматически разбивает трек по длинным
  разрывам (> 300 с) -- каждый вылет обрабатывается независимо. Решает
  проблему «уставшего backward-фильтра» на многочасовых треках с
  отключением аппаратуры между вылетами.
- **Ансамбль из 8 прогонов + Viterbi.** Комбинирует forward/backward
  прогоны с разными elevation mask (15 / 17 / 20 / 22 градуса).
  Превосходит одиночный RTKLIB на длинных baseline.
- **Backward-предпочтение.** На аэросъёмочных данных с длинными разрывами
  backward-решение превосходит combined/forward на 15--40 п.п. Q1.
- **Метаданные рядом с данными.** Anchor, координаты базы и дневные
  якоря хранятся в `.gnss_*.txt` в `Documents/`, не в конфигах.
- **Fail-fast.** Автоматический отказ при плохих входных данных (пустой
  RINEX, не тот тип файла, прерванный NovAtel Convert).

## Результаты (Julietta, 42+ проекта)

| Метрика | GrafNav 8.70 | Этот пайплайн |
|---|---|---|
| Средний Q1 | 78,0 % | **94,1 %** |
| Q1 на длинных baseline (> 80 км) | 51--59 % | **83--99 %** |
| Средний dH (Q=1) vs GrafNav | эталон | +/- 0,3 см |

## Требования

- **ОС:** macOS (протестировано на macOS 26 / Apple Silicon). Linux
  не тестировался.
- **Python:** 3.9+ (только stdlib; `plotly` опционально для
  экспериментальной визуализации).
- **RTKLIB-EX 2.5.1 (demo5)** -- готовые бинарники в `bin/`
  (macOS arm64).
- **NovAtel Convert** -- для конвертации `.NOV` в RINEX
  (протестировано через CrossOver на macOS).

## Установка

### 1. Клонировать

    git clone https://github.com/petrowmaxic/rtklib-ensemble-pipeline.git
    cd rtklib-ensemble-pipeline

### 2. Опционально: пересобрать бинарники RTKLIB-EX

Готовые `bin/rnx2rtkp_EX` и `bin/convbin_EX` собраны для macOS arm64.
Для других платформ -- собрать из исходников:

    git clone https://github.com/rtklibexplorer/RTKLIB.git
    cd RTKLIB/app/consapp/rnx2rtkp/gcc
    make
    cp rnx2rtkp /path/to/rtklib-ensemble-pipeline/bin/rnx2rtkp_EX

Аналогично для `convbin`. Детали версии -- в `docs/APPENDIX_D_env.md`.

### 3. Настроить пути

Отредактировать `conf/global.conf`:

    rover_root = ~/Documents/1_Data.nosync
    base_root  = ~/Documents/2_Diff.nosync

### 4. Опционально: зависимости Python

    pip3 install -r requirements.txt

## Быстрый старт

    # Один проект (интерактивно):
    ./scripts/pipeline.sh <rover.NOV> <base.ubx | base_dir>

    # Пакетная обработка:
    ./scripts/batch_ensemble.sh

Шаги пайплайна:

1. Конвертация базы UBX в RINEX, патч APPROX POSITION.
2. Конвертация ровера NOV в RINEX (NovAtel Convert).
3. Детект вылетов по разрывам > 300 с.
4. 8 прогонов RTKLIB на каждый сегмент, параллельно (N_JOBS=6).
5. Viterbi-объединение 8 прогонов внутри сегмента.
6. Склейка сегментов, экспорт в Oasis Montaj XYZ.

## Структура директорий

    rtklib-ensemble-pipeline/
      bin/              rnx2rtkp_EX, convbin_EX (macOS arm64)
      conf/             global.conf, FINAL.conf, STATIC.conf
      docs/             REPORT.md, JOURNAL.md, CHANGELOG.md, HOWTO_*
      scripts/          pipeline.sh, ensemble_viterbi.py, gnss_meta.py, ...
      STRUCTURE.md      полная структура проекта

Метаданные (anchor, координаты базы) хранятся рядом с исходными данными,
не в этом репозитории:

    <base_root>/<Area>/.gnss_anchor.txt
    <base_root>/<Area>/.gnss_base.txt
    <base_root>/<Area>/<YYYYMMDD>/.gnss_day_anchor.txt

Управляются через `scripts/gnss_meta.py` (`resolve`, `read-anchor`,
`read-base`, `check-area`).

## Документация

- `docs/REPORT.md` -- полный технический отчёт
- `docs/JOURNAL.md` -- хронологический журнал разработки
- `docs/CHANGELOG.md` -- история версий
- `docs/HOWTO_ANCHOR*.md` -- работа с anchor
- `STRUCTURE.md` -- структура проекта

## Цитирование

    Petrov, M. (2026). RTKLIB Ensemble Pipeline: open replacement for
    GrafNav in helicopter-borne aerosurvey.
    https://github.com/petrowmaxic/rtklib-ensemble-pipeline

## Лицензия

BSD 2-Clause -- см. [LICENSE](LICENSE). Совместима с RTKLIB-EX,
использующим ту же лицензию.

## Благодарности

- Tomoji Takasu -- RTKLIB
- rtklibexplorer (Tim Everett) -- RTKLIB-EX (demo5)
- NovAtel -- приёмники OEMStar / OEM7
- u-blox -- приёмники базовой станции
