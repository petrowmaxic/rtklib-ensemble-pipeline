# GNSS Experiment Pipeline -- Structure

Версия: v1.4.4 (2026-09-28)
Проект: Julietta, вертолётная аэросъёмка

## Дерево

gnss_experiment/
  bin/
    convbin_EX               -- UBX -> RINEX
    rnx2rtkp_EX              -- differential processing
    librtklib.dylib          -- RTKLIB-EX
  conf/
    global.conf              -- ЕДИНЫЙ конфиг путей (v1.4.0+)
    FINAL.conf               -- kinematic, L1, backward
    STATIC.conf              -- static (для anchor)
    ANCHOR_*.txt             -- LEGACY (мигрированы в Documents)
    base_ecef.txt            -- LEGACY (мигрирован)
  docs/
    REPORT.md, JOURNAL.md, CHANGELOG.md, VERSION, STRUCTURE.md
    APPENDIX_A..D.md, PROTOCOLS.md, GLOSSARY.md, HOWTO_*.md
  scripts/                   -- все скрипты
  cache/, logs/              -- рабочие (не в релизном архиве)

## Ключевые скрипты

  pipeline.sh              -- обработка одного проекта
  batch_ensemble.sh        -- batch проектов
  gnss_meta.py             -- API метаданных (v1.4.0+)
  gnss_area_init.py        -- мастер площади (v1.4.1+)
  migrate_day_anchors.py   -- миграция day-anchor (v1.4.2+)
  ensemble_segmented.py    -- сегментный ensemble (v1.3.0+)
  detect_segments.py       -- детектор gap (v1.3.0+)
  ensemble_viterbi.py      -- Viterbi merge
  export_v2.py             -- .pos -> .xyz
  generate_summary.py      -- summary
  compare_q1.py            -- сравнение с GrafNav
  detect_warmup.py         -- статика для anchor
  detect_anomaly.py        -- аудит подозрительных Q1 (v1.3.1+)

## Метаданные -- рядом с данными

  Documents/2_Diff.nosync/<Area>/.gnss_anchor.txt
  Documents/2_Diff.nosync/<Area>/.gnss_base.txt
  Documents/2_Diff.nosync/<Area>/<YYYYMMDD>/.gnss_day_anchor.txt

conf/ANCHOR_*.txt и conf/base_ecef.txt -- LEGACY, работают как fallback.

## Запуск

  gp <NOV> <base>            -- интерактивно
  gp <NOV> <base> "X Y Z"    -- неинтерактивно
  gnss_meta.py check-area <A>  -- валидация метаданных площади
