# Changelog

## [1.1.0] — 2026-09-25

### Роль anchor уточнена

Anchor работает как **tie-breaker между кластерами Viterbi**, не как критичный элемент.

**Экспериментальная проверка:**
- 42 проекта Julietta, anchor = (0,0,0) → Q1 = тот же, ΔQ1 = 0.00 %
- При ANCHOR_BONUS_MAX=20000 и сдвиге anchor на 1 км: RMS растёт с 1.13 до 1.77 м
- При BONUS=10 (дефолт): anchor ошибка до 1 км не ухудшает результат

### Автоматизация

- `auto_anchor.sh` — новый скрипт, получает anchor из прогрева ровера (1 час статики)
- `auto_anchor_from_workdir.sh` — быстрый вариант из готовых RINEX
- `pipeline.sh`: авто-получение anchor для первого вылета дня (YYYYMMDD или YYYYMMDD_1)
- `batch_ensemble.sh`: авто-получение anchor из первых 100 fix-эпох
- Приоритет поиска anchor: project > day > Julietta

### Исправления

- C1: ECEF через env BASE_ECEF
- C2: убран двойной viterbi_path
- C4: DOP по week+tow (не по индексу)
- V5: anchor обязателен (fail-fast) — переформулировано: anchor опционален, есть fallback
- V6: точный WGS-84 в ecef_dist
- V10: ratio = p[14]
- H4: timestamp + PID
- H7: max_jump ≤ 50 м

### Не проверено

- Hold-out валидация (см. PROTOCOLS.md)
- Кроссплатформенность Linux / Windows

## [1.0.0] — 2026-09-25

### Первый стабильный релиз

- 42 проекта Julietta обработаны end-to-end
- Средний Q1 = 92.6 %
- Точность fix: mean ±0.3 см / median ±0.02 см
- Метод: 8 прогонов rnx2rtkp + Viterbi

## [v1.4.7] -- 2026-09-29

### Изменено
- scripts/pipeline.sh: убрано дублирование даты в именах.
  - TIMESTAMP: было `%Y%m%d_%H%M%S_$$`, стало `%H%M%S_$$`.
  - OUTPUT_XYZ: `20260929_20260929_154257_50301.xyz`
              -> `20260929_154257_50301.xyz`.
  - WORK_DIR: `20260929_20260929_154257_50301/`
            -> `20260929_154257_50301/`.
  - merged.ubx: явный префикс с датой
    `merged_20260929_154257_50301.ubx` (дата полезна при нескольких днях).

### Причина
`TIMESTAMP` содержал `%Y%m%d`, который совпадал с `RUN_NAME` (датой).
Результат -- двойная дата в имени.

## [v1.4.6] -- 2026-09-29

### Изменено
- scripts/pipeline.sh:
  - ask_base принимает default -> при вводе базы предлагает GNSS_BASE_DIR.
  - Prefer merged.ubx: если в base_dir есть merged.ubx -- используется он,
    слияние пропускается. Иначе -- сливаются все *.ubx как раньше.
  - .NOV extension check: если ровер не .NOV -- предупреждение и prompt
    "Продолжить всё равно?" (защита от случайного выбора .xyz).
- scripts/batch_ensemble.sh:
  - Удалён мёртвый блок auto-day-anchor (обращался к ensemble/*.pos,
    которых нет с v1.3.0).

### Проверка
- 20260929: Q1 = 83.15 % (GrafNav 55.5 %), 165709 эпох, 6 сегментов.
- Prompt базы: Enter принимает default (Julietta/20260929).

## [v1.4.5] -- 2026-09-28

### Диагностика
Проверены 3 day-anchor с WARN в check-area Julietta:

| дата | day anchor h | result.pos начало h | вывод |
|---|---|---|---|
| 20260825 | 329.78 | 832.48 (Q1 стабильно) | anchor ошибочный |
| 20260830 | 993.47 | 832.49 (Q1 стабильно) | anchor ошибочный |
| 20260902 | 874.57 | 832.52 (Q1 стабильно) | anchor ошибочный |

**result.pos** во всех трёх случаях начинается с h ~ 832.5 = area anchor
Julietta (832.4611). Ровер стоял на площадке, данные корректны.
Ошибочен именно day anchor -- авто-детектор detect_warmup брал первые
100 Q1 без проверки "на земле".

### Изменено
- Удалены все 24 day anchor Julietta из
  Documents/2_Diff.nosync/Julietta/<date>/.gnss_day_anchor.txt.
- Бэкап: Documents/2_Diff.nosync/Julietta/.day_anchor_backup_<ts>/.
- Обоснование: вертолёт утром всегда взлетает с одной и той же площадки
  (методические работы по калибровке гамма-спектрометра). Area anchor
  покрывает все случаи; day anchor -- либо совпадает с area (21 файл),
  либо явно ошибочен (3 файла).

### Проверка
- gnss_meta.py check-area Julietta: OK=3, WARN=0, ERR=0.
- gnss_meta.py read-anchor: priority=area (fallback работает).
- find .gnss_day_anchor.txt -> 0.

### TODO v1.4.6
- detect_warmup.py: добавить ground-check (h_static в пределах +-30 м
  от area anchor). Иначе -- отклонить статику как "ровер в воздухе".
- batch_ensemble.sh: удалить мёртвый блок auto-day-anchor.

## [v1.4.4] -- 2026-09-28

### Добавлено
- gnss_experiment/STRUCTURE.md -- структура пайплайна, ключевые скрипты, метаданные.
  - Заменяет устаревший STRUCT.md (от 25 сентября) -> STRUCT.md.legacy.
- Documents/1_Data.nosync/Julietta/STRUCTURE.md -- структура rover-данных,
  соглашения именования, метаданные в base_root.
- Documents/2_Diff.nosync/Julietta/STRUCTURE.md -- перезаписан
  (был сломан tree-отступами от gnss_area_init.py v1.4.1).
  - Исправлено дерево, добавлены приоритеты anchor, известные наблюдения.

### Известные наблюдения
- 3 WARN в check-area Julietta (20260825/20260830/20260902) включены
  в base_root/STRUCTURE.md. См. TODO v1.4.5.

## [v1.4.3] -- 2026-09-28

### Изменено
- scripts/pipeline.sh: интеграция с gnss_meta.py.
  - Резолв путей через `gnss_meta.py resolve` -> GNSS_AREA, GNSS_PROJECT,
    GNSS_DATE, GNSS_ROVER_NOV, GNSS_ROVER_DIR, GNSS_BASE_DIR и др.
  - ECEF базы: `gnss_meta.py read-base` (fallback на интерактив).
  - Anchor: `gnss_meta.py read-anchor` (priority day -> area -> legacy).
  - Fail-fast если rover.26O < 1 МБ (защита от прерванного NovAtel Convert).
  - Строка шага 3.5 обновлена на (v1.4.3).
  - Все изменения с fallback: если gnss_meta.py нет, работает legacy.

### Регрессия
- 20260927: Q1 = 97.01 %, 192290 эпох, 4 сегмента, DOP OK.
- Идентично v1.3.1 (baseline).
- ECEF и anchor помечены `(gnss_meta)` — источник подтверждён.
- Время прогона 253 сек (v1.3.1 было 254 сек).

## [v1.4.2] -- 2026-09-28

### Добавлено
- scripts/migrate_day_anchors.py -- миграция conf/ANCHOR_<YYYYMMDD>.txt в <base_root>/<Area>/<YYYYMMDD>/.gnss_day_anchor.txt.
- Флаги: --area, --dry-run, --force, --mark-migrated, --no-backup.

### Миграция
- Julietta: 24 day anchor перенесены из conf/ в новую структуру.
- gnss_meta.read_anchor возвращает priority=day для этих дней.

### Наблюдения (3 WARN)
- check-area Julietta: 24 OK, 3 WARN, 0 ERR.
- 20260825: 101549 м от area anchor, dh = -502.7 м (другая площадка?).
- 20260830: 1654 м, dh = +161.0 м (ровер в воздухе при auto-anchor).
- 20260902: 809 м, dh = +42.1 м (то же).
- См. TODO v1.4.5.

## [v1.4.0] — 2026-09-28

### Добавлено
- `conf/global.conf` — единый конфиг путей (rover_root, base_root, outputs_root, batch_root, n_jobs, segment_gap_sec).
- `scripts/gnss_meta.py` — единый API метаданных GNSS:
  - `detect_paths(nov)` — авто-детекция Area / Project / Date / ROVER_DIR / BASE_DIR из пути `.NOV`.
  - `read_anchor` / `read_base` / `read_day_anchor` — приоритет: day → area → legacy conf/.
  - `wgs84_to_ecef` / `ecef_to_wgs84` — WGS84 ↔ ECEF.
  - `check_area(area)` — валидация метаданных площади.
  - CLI: `resolve`, `read-anchor`, `read-base`, `read-day-anchor`, `check`, `check-area`.

### Изменено
- Метаданные переезжают к данным:
  - Anchor площади → `1_Data.nosync/<Area>/.gnss_anchor.txt`
  - Координаты базы → `2_Diff.nosync/<Area>/.gnss_base.txt`
  - Дневной якорь → `2_Diff.nosync/<Area>/<YYYYMMDD>/.gnss_day_anchor.txt`
- Формат метаданных — key=value с `#`-комментариями.

### Legacy
- `conf/ANCHOR_*.txt`, `conf/base_ecef.txt` остаются как fallback (priority: legacy).
- Миграция в v1.4.2 через отдельный скрипт.

## [v1.3.1] — 2026-09-28

### Исправлено
- `generate_summary.py`: `compute_fwd_bwd_sep` и `compute_drift_vs_bwd` агрегируют **по всем сегментам** (раньше — по первому). Coverage корректный (~90 % вместо 14 %).
- `batch_ensemble.sh`: `pipeline_ensemble.sh` вызывается **только если** `rover.26O` или `base_surveyed.26O` отсутствуют. Экономия ~2 мин на «свежих» проектах.
- `batch_ensemble.sh`: `.stat` перезаписывается при повторном прогоне (была проверка `[ ! -e ]`).
- `batch_ensemble.sh`: N_POS проверка убрана (`ensemble/` больше не используется).
- `generate_summary.py`: пороги под multi-segment reality.
  - Coverage: 90/70 → **85/60** (69 % на 4-сегментном треке — норма).
  - Drift: считается по **median**, а не по mean. Пороги 0.05 / 0.30 м.
  - Обоснование: при агрегации по 4 сегментам данные честнее, и mean
    дрейфа включает пограничные эпохи у краёв сегментов.

### Не затронуто
- Логика сегментации (`ensemble_segmented.py`) не менялась.
- Q1/mean регрессию не запускали — изменились только метаданные summary и batch-скорость.

### TODO v1.3.2
- 20260825_2: `max_abs` +2.9 м при улучшенном `mean_all` и RMS. Локальная аномалия 26 сек в 02:58:17–43.

### Known limitations
- 20260825_2, 02:58:17-02:58:43 GPST. Локальная аномалия: 26 сек, ошибка до 25 м, вызвана структурным расхождением forward/backward после многократных разрывов сигнала. Viterbi выбрал единственный доступный Q1 от e22_backward, оказавшийся ложным.
- Автоматический demote-критерий (MAD-based, k > 50 AND MAD < 0.5 AND run-length <= 60 с) показал 82 % detection и 0 % false positive на контрольных проектах, но не внедрён — требует hold-out валидации на новых данных.
- Добавлен опциональный скрипт scripts/detect_anomaly.py для ручного аудита (не изменяет result.pos).

## [v1.3.0] — 2026-09-27

### Добавлено
- `detect_segments.py`: парсит RINEX obs, находит gaps > 300 сек, возвращает список сегментов.
- `ensemble_segmented.py`: сегментная обработка (8 прогонов rnx2rtkp с -ts/-te на сегмент + Viterbi + склейка `.pos` и `.stat`).
- `PROJECTS_OVERRIDE` в `batch_ensemble.sh` — запуск batch на подмножестве проектов.

### Изменено
- `pipeline.sh`: шаги [3.5/5] + [4/5] заменены на один вызов `ensemble_segmented.py`.
- `batch_ensemble.sh`: использует `ensemble_segmented.py` вместо `ensemble_viterbi.py`.
- `generate_summary.py`: `_auto_ensemble_dir` возвращает список директорий (`ensemble/` или `seg_*/`).

### Результат
- Batch на 42 проектах: средний Q1 93.0 % → 94.1 %, mean_all 0.22 см → 0.11 см.
- Ключевые кейсы: 20260918_2 (mean −0.96 → +0.11 м, max 118 → 3.81 м), 20260818_1 (Q1 87.4 → 99.96 %), 20260901_1 (max 88.6 → 4.26 м).

### Обоснование
Раздельные вылеты после отключения оборудования = сброс integer. Длинный backward-фильтр накапливает систематический сдвиг за 5 часов трека. Сегментация даёт свежий forward и backward в каждом вылете.

### TODO v1.3.1
- `Coverage` в summary по одному сегменту (ложный ALERT).
- Batch: убрать лишний `pipeline_ensemble.sh` перед `ensemble_segmented.py`.
- `.stat`: перезаписывать при повторном прогоне.
- `compute_drift_vs_bwd`: агрегировать по всем `seg_*`.

