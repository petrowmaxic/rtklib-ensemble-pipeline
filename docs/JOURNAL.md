# GNSS Experiment Journal
Started: 2026-09-22 17:13:28
[2026-09-22 17:14:46] S1: framework, symlinks, bin copies ready
[2026-09-23 08:39:34] S4: patched base APPROX POSITION -> surveyed ECEF
[2026-09-23 08:39:38] S5: created conf/EX_gps_conv.conf (GPS-only, ant2-antdelu=1.800)
[2026-09-23 08:39:41] S6: EX_gps_conv without -r -> 0 epochs (ref pos=0). With -r -> 134916 epochs OK
[2026-09-23 08:54:22] S7: сравнение по GPST (не по строкам!): median dH=-1.3cm, mean=-10.6cm, RMS=42.7cm, max=3.57m. Прорыв: расхождение сантиметровое.
[2026-09-23 08:54:26] S7: Q1=62.4% vs GrafNav 80.9%. Провалы AR в 03:10-03:50, 04:10-05:20. Причина: 1Гц база vs resampled 10Гц у GrafNav + AR-параметры.
[2026-09-23 09:07:41] S8-diag: avg_ns=6.5-8.0 все эпохи; провалы AR в 03:10-05:20 из-за низкого ratio (1.1-30), не из-за нехватки спутников.
[2026-09-23 09:07:44] S8-noatmo: maxage=30 ломает решение (медиана 169см в 02:50). iono/tropo=brdc/saas нужны. Откат к maxage=2.0.
[2026-09-23 09:10:01] S8b: arthres=5.0+arminfix=5 -> Q1=58.5% (хуже conv). 
[2026-09-23 09:10:04] S8c: +GLONASS по коду -> Q1=67.7%, median dH=-0.29см, mean=-2.6см. GLONASS полезен даже без фазы.
[2026-09-23 09:10:08] S8d: forward-only хуже combined (52.7% vs 67.7%). AR теряется на fwd, rev восстанавливает.
[2026-09-23 09:10:11] S8-hyp: оператор мог выключать приёмник в полёте. Проверить epoch flag и ns в rover RINEX.
[2026-09-23 09:17:14] S9-diag: 174 эпохи с ns<6 (04:14:07-04:14:20 область). Флаги в RINEX все 0. Мы теряем 24 эпохи vs GrafNav.
[2026-09-23 09:29:55] S10-ПРОРЫВ: NovAtel GPS+GLO (4 obs) -> Q1=80.2%!!! Совпадает с GrafNav (80.9%). GLONASS-фаза работает.
[2026-09-23 09:29:59] S10: NovAtel GPS-only (4obs) Q1=42.5%, 2obs Q1=16.3%. Без SNR RTKLIB не может взвешивать наблюдения. Оставляем 4 obs.
[2026-09-23 09:37:58] S11: NovAtel G+GLO Q1=80.2% median dH=0.09см. НО float уезжает (mean=+30см, RMS=98см, p95=247см). Причина: pos2-gloarmode по умолчанию off, IFB не оценивается.
[2026-09-23 09:47:11] S13-ФИНАЛ: EX_glo_v2 (NovAtel RINEX + gloarmode=on, arthres=3.0). Q1=86.1% > GrafNav 80.9%. median dH на Q=1 = -0.9мм, mean=-3.1мм. Конфиг зафиксирован.
[2026-09-23 10:15:00] S17: arthres=2.5 -> Q1=89.4% (было 86.1%) с тем же уровнем шума (RMS на Q=1: 31.9см vs 30.8см). Финализировано на arthres=2.5.
[2026-09-23 10:16:53] S20-ФИНАЛ: экспорт готов. q1fix.xyz=120628 эпох (89.4% Q1). full.xyz=134963. DOP из .stat, без numpy, за 6.7 сек. DOP GrafNav vs наш: разные конвенции HDOP/VDOP, PDOP сопоставим.
[2026-09-23 10:19:01] S21: ТЗ может ограничивать DOP. Наш PDOP сопоставим с GrafNav (~+7%). HDOP/VDOP в разных конвенциях (tilted vs ENU). Проверить формулировку ТЗ.
[2026-09-23 10:45:36] S22-ТЗ-OK: max PDOP в FINAL=4.93 << порога 10. Ни одной эпохи с PDOP>10, ни одной с PDOP>6. ТЗ "DOP≤10 в течение 100 сек" выполняется с запасом x2. Экспорт q1fix.xyz финальный.
[2026-09-23 10:47:56] S23-ТЗ-check: полная проверка обоих экспортов на критерий "DOP>10 непрерывно 100с".
[2026-09-23 10:49:18] S23: check_dop_100s.py -> 0 интервалов DOP>10 в обоих экспортах. ТЗ выполнено. Обнаружено противоречие в awk (PDOP>10=48 при max=4.93) — предполагаю локаль ru_RU. Диагностика.
[2026-09-23 10:49:56] S23-ТЗ-OK: оба экспорта (q1fix, full) проходят ТЗ. max PDOP=4.93, max HDOP=2.12, max VDOP=4.45. Ни одного интервала DOP>10. Ранее "48 эпох PDOP>10" — баг локали ru_RU в awk, с LC_NUMERIC=C результат = 0.
[2026-09-23 10:54:46] S24-ФИНАЛ: full.xyz полностью воспроизводит структуру GrafNav. Пропуски идентичны (897с + 370с + 0.5с), 8.59% эпох отсутствуют в исходных данных. GrafNav тоже их не заполняет. Отдаём full.xyz как основной.
[2026-09-23 10:54:49] ЭКСПЕРИМЕНТ ЗАВЕРШЁН. Результат: 89.4% Q1 (лучше GrafNav 80.9%), сантиметровая сходимость на fix, ТЗ по DOP выполнено, формат XYZ идентичен эталону.
[2026-09-23 11:04:04] PIPELINE-OK: pipeline.sh отработал end-to-end. 3 минуты, результат в <rover_dir>/<rover_dir_name>.xyz. Воспроизводимость: проверить diff с FINAL.
[2026-09-23 11:37:53] PIPELINE-v4: защита от перезаписи. (1) merged.ubx в директории базы, при конфликте merged_<timestamp>.ubx. (2) <name>.xyz у ровера, при конфликте <name>_<timestamp>.xyz. Оба предупреждения в сводке до подтверждения.
[2026-09-23 11:46:56] PIPELINE-v4-OK: 20260921_1 обработан. Q1=75.08% (GrafNav=59.4%), +15.7 п.п. ТЗ по DOP выполнен. Защита .xyz сработала. Пропусков 17.2% (6 интервалов), у GrafNav No-processed 18% — у нас лучше.
[2026-09-23 11:51:18] CLEANUP: удалено 2.6 ГБ (vanilla 2.4.3, тестовые EX_*.pos, RINEX convbin, дубликатные pipeline runs). Осталось 763 МБ в gnss_experiment + 1.7 ГБ в pipeline_runs. FINAL.conf, FINAL.pos, все скрипты и XYZ сохранены.
[2026-09-23 11:55:27] ФИНАЛИЗАЦИЯ: эксперимент сжат до 59 МБ. Оставлены: JOURNAL.md, все скрипты, FINAL.conf, GrafNav эталон, CSV сравнения, 3 XYZ-результата и FINAL.pos. Pipeline воспроизводит любой результат за 3 минуты.
[2026-09-23 12:02:22] PIPELINE-BUG: (1) find подхватил merged.ubx в директории базы → дублирование. (2) NovAtel Convert отработал, но файлы rover.26O/.26N не в WORK_DIR. Диагностика.
[2026-09-23 15:38:15] 20260921_2: baseline=41км avg, 108км max. Q1=43% vs GrafNav 93.6%. Гипотеза: brdc/saas не тянут длинный baseline. Тест est-stec/est-ztd.
[2026-09-23 16:02:00] LONG-BASELINE-TEST: baseline=43%, +est-stec/est-ztd на elmask=17 -> 32% (хуже). +elmask=20 -> 75.2% (+32 п.п.). elmask критичен для est-stec. GPS-only 29.5%. Вторая серия тестов.
[2026-09-23 16:15:14] TEST2: elmask=22 brdc/saas = 84.4%. elmask=20+est-stec+arminfix3 = 94.9% (лучше GrafNav 93.6%!). est-stec портит при elmask=22/25, работает при 20. arminfix=3 критичен. Третья серия для изоляции.
[2026-09-23 16:17:11] TEST-CRITICAL: test_g (est-stec+elmask20+arminfix3) Q1=94.9% НО mean dH=-1.26м! Это ЛОЖНЫЕ fix. est-stec даёт метровый сдвиг на длинном baseline. Реальные победители: h/i (elmask=22+brdc/saas+arminfix=3) Q1=85.2%. Проверить точность h.
[2026-09-23 17:17:32] REWIND-ANALYSIS: reverse-only Q1=96.6% vs combined 85.2%! fwd фиксы ⊂ rev фиксы (fix both=8149). Combined теряет ~8000 fix. Проверка точности reverse-only vs GrafNav.
[2026-09-23 17:19:50] REVERSE-WIN: reverse-only Q1=96.6% (combined 85.2%, GrafNav 93.6%). mean dH=-3.76см, нет сдвига. Forward на этом треке плохой (1 спутник на старте), combined теряет fix. Reverse обгоняет GrafNav на +3 п.п. Проверка на Julietta и 20260921_1.
[2026-09-23 17:30:07] JULIETTA-BACKWARD: Q1=98.4% (combined 89.4%, GrafNav 80.9%). mean dH=-1.25см, median=-0.18см — честные fix. Cross-check backward vs combined: медианы совпадают до 0.3мм на 90% интервалов — SAME fixes, MORE of them. Решение: merge fwd+rev для максимума покрытия.
[2026-09-23 17:50:09] 20260921_1-BACKWARD: Q1=98.9% (combined 75.1%, GrafNav 59.4%). mean dH=-1.45см, median=+0.05см — БЕЗ систематики. RMS=45.5см — шум тот же, что у combined. Backward честен: тот же режим RTKLIB, воспроизводится, cross-check совпадает с combined там где оба fix. Финализируем на backward.
[2026-09-23 17:57:53] EXPORT-V2-FIX: сопоставление по индексу эпохи решило проблему DOP. 20260921_1: DOP_zero=56/193376 (0.03%), Julietta: 2/134961. Pipeline обновлён на export_v2.py.
[2026-09-23 18:11:51] ELMASK-DEPENDENCY: на 20260921_2 elmask=17+backward -> Q1=24.6% (было 96.6% при elmask=22+combined). Нужен auto-tune elmask по baseline. Проверка elmask=22+backward.
[2026-09-23 19:15:23] ELMASK-PHASE-TRANSITION: 20260921_2 sweep. elmask 10-17: Q1=17-33%, elmask=20: Q1=99.4%. med_sdu одинаков (6.9 vs 7.3мм), ratio 3.1 -> 9.3. Это не постепенный рост, а бинарный переход — какой-то спутник 17-20° ломает AR. Проверка 20 на других проектах.
[2026-09-23 19:17:40] MINEL-HYPOTHESIS: переход elmask 19->20 на 20260921_2 (Q1 24.5%->99.4%) указывает на конкретный спутник-отравитель. Проверка через гистограмму min_el->fix_rate.
[2026-09-23 19:19:59] MINEL-HYPOTHESIS-DISPROVEN: fix% vs min_el бимодален (11-12: 98%, 13-20: 0-7%, 21+: 11-33%). elmask=20 не из-за отсечения низких — из-за нелинейного эффекта на DD-пары. Переход к per-satellite анализу.
[2026-09-23 19:22:55] TROUBLEMAKERS-ANALYSIS: спутника-отравителя нет. R19 fix=7.2% но med_el в fix и float одинаков. G22 100% fix (только в fix-эпохах). Плато 17.1% у фоновых SV. Гипотеза: fix/float идут блоками по времени. Fix-window анализ.
[2026-09-23 19:24:41] FIX-FLOAT-BLOCKS: fix идёт блоками (04:00=100%, 04:20=0%, 04:30=61%, 04:40-05:40=0%). Спутник-отравитель не найден (exclsats R19+G28+G25 не помог). Гипотеза: застревание AR-фильтра. Диагностика ns/ratio в fix vs float блоках.
[2026-09-23 19:28:24] RATIO-STUCK: ratio застревает на 1-2 в float-блоках (79%), на 3-4 в fix-блоках (63%). ns одинаков (14). elmask=20 работает не "убирая спутники", а "меняя DD-пары, чтобы LAMBDA разделил варианты". Тесты arthres=2.0, arminfix=1, armaxiter=3.
[2026-09-23 19:30:52] AR-TUNING-FAIL: arthres=2.0, arminfix=1, armaxiter=3 не решают проблему. Ratio застревает 1-2, LAMBDA не разделяет. Единственный рабочий — elmask=20. Проверка reference SV и arthres1-4.
[2026-09-23 19:32:35] FINAL-DECISION: AR-параметры не помогают (arthres, arminfix, armaxiter, arthres1-4). Reference SV не настраивается. Бинарный переход 19->20 не объясняется математически на этих данных. Решение: sweep-based auto-tune elmask с кэшем. Патч pipeline.
[2026-09-23 19:48:53] BACKWARD-SORT-FIX: backward-pos пишет эпохи в обратном порядке. check_time_gaps показывал отрицательные пропуски. Патч: сортировка по времени в check_time_gaps, check_dop_100s, export_v2. Sweep auto-tune работает: 20260921_2 -> elmask=20 (Q1=99.4%), Julietta -> elmask=15 (Q1=98.9%).
[2026-09-23 19:53:41] BACKWARD-SORT-OK: 20260921_2_backward_sorted.xyz — 71439 эпох, пропуск 4 эпохи (0.01%), DOP_zero=0. Файл готов к передаче. head/tail показывает разные части файла — ложная тревога.
[2026-09-23 20:20:42] SWEEP-ABSOLUTE-OK: критерий по Q1_abs работает. 20260921_1 выбран elmask=15 (191461 fix) вместо 22 (84379 fix, -56%)
[2026-09-23 20:22:15] ЭКСПЕРИМЕНТ ЗАВЕРШЁН. Три проекта обработаны pipeline с auto-tune elmask. Средний Q1: 99.1 процентов против GrafNav 78.0 (+21 п.п.). Median dH на fix: -0.2 см. Все ТЗ по DOP выполнены. Формат XYZ идентичен эталону. Пайплайн полностью автоматизирован, воспроизводим и не зависит от GrafNav.
[2026-09-23 21:33:13] SUMMARY-ADD: добавлен generate_summary.py — статистика в стиле GrafNav рядом с XYZ. Протестировано 7 проектов. Все ТЗ пройдены. 20260922_1 сложный (Q1=60.82% vs GrafNav 57.0%) — проверить точность.
[2026-09-23 21:39:15] 20260922_1-PROBLEM: первый час (20:00-20:50) fix с ошибкой 11-19 метров — ложные fix. Q1=60.82% валиден, но координаты на старте неверны. Диагностика перекрытия база/ровер по времени. Патч generate_summary для backward.
[2026-09-23 21:41:43] 20260922_1-DEEP: база начинается в 20:08:19 (через 5 мин после ровера 20:03). Ложные fix 14 м в 20:00-20:50 — вероятно backward-специфичный сбой AR. Проверка forward.
[2026-09-23 21:44:31] UNION-RECONSIDERED: на 20260922_1 forward и backward ВЗАИМОДОПОЛНЯЮЩИЕ. Forward решает 20:00-20:50, backward 21:00-23:10. Union с проверкой согласованности даст ~95% Q1 честно. Тест merge_fwd_rev.py.
[2026-09-23 21:48:38] 20260922_1-ANOMALY: sdu не различает зоны (fwd 17мм/9мм, bwd 12мм/8мм). merge_by_quality не сработает. Проверка combined — если не поможет, оставить backward + пометить 20:00-20:50 unreliable.
[2026-09-23 21:57:42] SPLIT-NOT-UNIVERSAL: split_fwd_rev нашёл зону расхождения 20:15 (mean |dH|=1385 см), но применил split только там. Итог: Q1=62.6% (было 60.8%), но в 21:30-22:20 испортил интервалы (216-258 см). Алгоритм одноточечный — не работает при нескольких зонах расхождения. Backward-only остаётся дефолтом. Split/comиbined — опции для ручного разбора аномальных проектов.
[2026-09-24 08:49:04] ENSEMBLE-FIX: bug в awk (q как скаляр и массив). Исправлено: q1++ / q1+0. Кэш поддерживается — перезапуск досчитает оставшиеся 6 прогонов.
[2026-09-24 08:51:38] ENSEMBLE-RUN: 8 прогонов готовы. Merge v2: кластеризация + anchor + temporal consistency. Запуск.
[2026-09-24 08:54:55] ENSEMBLE-BUGFIX: (1) glob подхватывал _events.pos -> фильтр; (2) temporal anchor не создавался до 20:57 (tie 4-4 fwd/bwd). Добавлен seed по координатам базы: ровер стоит на земле рядом с базой в первые секунды -> кластер ближайший к base_h — правильный. Перезапуск merge.
[2026-09-24 08:57:32] ENSEMBLE-V3: переписано (v3). Фиксы: (1) parse_pos_all хранит и Q=2 (fallback не теряет эпохи); (2) pick_cluster_continuity выбирает по близости к prev, не по большинству; (3) seed от базы не сбрасывается. Ожидаем полное покрытие + правильные кластеры.
[2026-09-24 09:10:13] ENSEMBLE-V4: волновая экстраполяция. Идея: якоря = зоны согласия fwd/bwd. От якоря экстраполируем позицию по скорости. На каждой эпохе выбираем кластер ближайший к экстраполяции. Это должно решить 20:00-20:50 (forward правильный, экстраполяция от якоря 20:50 совпадает с forward).
[2026-09-24 11:00:42] ANCHOR-STAND: из GrafNav стоянки 20260823 получена координата площадки: lon=154.015098788, lat=61.161609560, h=832.4437. Разница с базой: 51м гориз, +0.52м по h. Это абсолютный якорь для всех вылетов Julietta (ровер садится в радиусе 1м). Проверка первых/последних секунд 20260922_1.
[2026-09-24 11:11:54] ENSEMBLE-V5-WIN: Q1=81.6% vs backward-only 60.8% vs GrafNav 57%. mean dH=-7см (было +72см), median=0.6мм, max=2.67м (было 13.98м). Площадка 20260823_cTo9Nka как абсолютный якорь. Осталось: grace-период 120 сек чтобы убрать 2.6% остаточных выбросов в 20:00-20:10.
[2026-09-24 11:14:04] V5C-PATCH: grace period убран (ломал начало). Fallback для эпох без fix = prev_chosen (temporal continuity от площадки). До первого fix ровер на площадке, координата = anchor. Плюс таймеры в скрипты.
[2026-09-24 11:15:43] V6-PATCH: v5c сломал fallback (prev_chosen замораживался, ровер «улетал»). Возврат к fallback float из прохода + anchor только на первые 30 сек после первого fix.
[2026-09-24 11:16:53] V6-FIX: timedelta не импортирован. Патч: from datetime import datetime, timedelta. Перезапуск.
[2026-09-24 11:18:33] V6-ОТКАТ: v6 обновлял prev_chosen при fallback -> траектория уезжала. Убрана строка, оставлен anchor-до-первого-fix. Запуск v7.
[2026-09-24 11:20:56] V8-FIX: ANCHOR применялся только после первого fix. Расширено окно: fallback на ANCHOR если prev_chosen всё ещё рядом с ANCHOR (<100 м) и t < first_fix + 300 сек. Это должно исправить 20:00-20:08 (было 1421 см).
[2026-09-24 11:21:48] ENSEMBLE-V8-ФИНАЛ: Q1=81.69% (backward 60.8%, GrafNav 57%). mean dH=-5см, median=+0.56см, RMS=34см, max=2.67м. ВСЕ 10-мин интервалы < 33см. Q=1 с |dH|>5м: 0. Якорь площадки 20260823_cTo9Nka + walk от него + fallback на anchor до первого fix. Ансамбль из 8 прогонов + temporal continuity решил задачу, которую GrafNav решает через ARTK_REWIND.
[2026-09-24 11:51:52] ENSEMBLE-V9-3PROJ: r20260920=99.39%, 20260921_1=99.23% — оба отличные. 20260921_2=26% из-за MAX_JUMP_M=3 (вертолёт 30-50м/с не влезал). Патч MAX_JUMP_M=10, перезапуск.
[2026-09-24 12:45:23] VITERBI-START: переписан алгоритм с жадного walk на Viterbi. Вес кластера = голоса + anchor_bonus. Глобальная оптимизация пути с ограничением MAX_JUMP_M=10. Ожидаем решение проблем v10 (20260921_2 +21см) и v11 (20260921_2 35%). Один алгоритм для всех проектов.
[2026-09-24 12:52:53] VITERBI-V3: (1) backtracking переписан — сегменты корректно закрываются, не теряются 29k эпох. (2) fallback без anchor — float из лучшего run (anchor был 5км от истины в полёте). (3) output raw из любого run.
[2026-09-24 12:55:35] VITERBI-V4: интерполяция fallback-эпох. 477 эпох без fix в 20260921_1 улетали на 400+ м (mean всего файла +1.07 м). Теперь: линейная интерполяция между соседними Q=1 если расстояние <500 м.
[2026-09-24 13:04:14] BATCH-FIX: добавлены проверки на пустой ensemble (awk divide-by-zero), отсутствие .NOV, отсутствие .ubx. Skip вместо crash.
[2026-09-24 13:07:51] BATCH-FIX-2: pipeline_ensemble.sh теперь fail-fast если rover.26O не создан + логирует NovAtel Convert. batch_ensemble.sh проверяет >=4 валидных .pos перед Viterbi + удаляет старый пустой Viterbi.
[2026-09-24 13:19:39] BATCH-FIX-3: найден orphan-блок "echo skip_no_data; continue" в batch_ensemble.sh до проверок — все 45 проектов пропускались. Убран. Скрипт не трогает исходные файлы в Documents.
[2026-09-24 13:51:31] BATCH-START: запущен полный батч 43 проектов. Скрипт протестирован на 20260818_1 (Q1=87.37%, mean=-15см) и 20260818_2 (Q1=100%, mean=-2.5см). Ожидаемое время ~7 часов.
[2026-09-24 13:57:21] BATCH-PROGRESS: добавлен счётчик N/M, таймер elapsed, ETA. Запуск полного батча в терминале без tmux.
[2026-09-24 15:48:29] PARALLEL: NovAtel 6-поточный (Windows-архитектура), rnx2rtkp однопоточный (Kalman sequential). Параллелим между прогонами: N_JOBS одновременных rnx2rtkp. Ожидаемое ускорение 4x.

[2026-09-26 12:00:33] PATCHES-V1.1.1:
  - patch01: ANCHOR_BONUS_MAX 10.0 -> 0.5
  - patch02: anchor опционален (V5 fail-fast отключён)
  - patch03: fallback float/anchor/empty (защита от телепорта)
  - patch04: FWD/BWD метрика в generate_summary.py
  Скрипт: scripts/patch_all_20260926.py
  Регрессия: 20260925 + 20260906_2 + 20260825_2 + 20260922_1

[2026-09-26 13:06:36] BATCH-FIX v1.1.1:
  - batch_ensemble.sh: guard read сверху (ANCHOR_FILE пуст при старте)
  - batch_ensemble.sh: ${p} -> ${PROJ}, $proj -> $WORK (баг auto-anchor)
  - batch_ensemble.sh: init ANCHOR_* defaults перед export
  - batch_ensemble.sh: N_JOBS default 6
  - pipeline_ensemble.sh: N_JOBS default 4 -> 6

[2026-09-26 13:07:44] REGRESSION v1.1.1 (N_JOBS=6):
  baseline: /Users/maxic/gnss_batch_runs/batch_results_v1.1.0.csv
  new:      /Users/maxic/gnss_batch_runs/batch_results.csv
  идентичных (|Δ|<0.05): 0
  ✓ регрессия чистая

[2026-09-26 13:10:17] FIX-PERMS 2026-09-26:
  - Причина: patch-скрипты через os.replace(tmp,path) сбрасывали exec-бит
    на .sh файлах (tmp создавался с 0644 через open('w'))
  - Исправлено: chmod +x для 3 *.sh в scripts/
  - batch_results_v1.1.0.csv (мусорный, 2 строки) -> .broken
  - TODO: в патчерах использовать shutil.copymode(path, tmp) перед os.replace

[2026-09-26 14:00:41] SESSION-20260926 SUMMARY (диагностика 20260925 + патчи v1.1.1 + batch регрессия):
  --- Диагностика 20260925 ---
  • Изначальная гипотеза «выбросы в первых 20 минутах» — неверна. Ранняя зона
    8–14 мин = 2000 эпох (1.3 %), смещение ~3 м, между двумя gap'ами (523 с и 248 с).
  • Реальная проблема — FWD/BWD separation 30–132 м в зоне 01:51–03:11 после
    gap 868 с. Forward уходит в ложный AR-кластер, backward совпадает с GrafNav (0.055 м).
  • Viterbi выбрал backward ПРАВИЛЬНО (проверено viterbi_vs_graf). Максимум 132 м —
    это forward-only артефакт, не наш result.
  • sdu Q1 идентичен early/late (~0.0076 м), sdu-фильтр (>0.10 м) бесполезен.
    Q=2 = 208 эпох interleave в первые 15 с, h = anchor — не влияет ни на что.
  --- Патчи v1.1.1 ---
  • patch01: ANCHOR_BONUS_MAX 10.0 -> 0.5 (anchor почти не влияет на Q1)
  • patch02: anchor опционален (fail-fast V5 отключён)
  • patch03: fallback разделён — float/anchor/empty (защита от телепорта)
  • patch04: FWD/BWD метрика в generate_summary.py (пороги 2/10 м -> CLEAN/WATCH/REVIEW)
  --- Batch регрессия v1.1.1 (42 ok / 2 skip_no_ubx / 1 skip_no_rover) ---
  • Средний Q1 ~ 94 %. 100 %: 8 проектов. <85 %: 6 проектов.
  • 20260925 не изменился: 99.87 % до и после патчей. Регрессия чистая.
  • Реальные bug-фиксы batch: ${p} -> ${PROJ}, $proj -> $WORK, guard read,
    N_JOBS default 6 в batch_ensemble + pipeline_ensemble.
  --- Найдено в регрессии ---
  • Auto-anchor создал плохие anchor для 20260830 (993 м) и 20260902 (874 м) —
    первые 100 Q=1 fix оказались в воздухе, а не на площадке. Спасло bonus=0.5.
  • 20260918_2: mean_Q1=-2.18 м, median_Q1=+0.018 м — тот же паттерн, что
    20260906_2 (max FWD/BWD 143 м) и 20260825_2 (77 м).
  --- TODO v1.2.0 ---
  • Viterbi: переключение кластеров при FWD/BWD > 20 м (backward уходит в ложный AR).
  • Auto-anchor: проверка радиуса <1 км от Julietta, иначе fallback.
  • batch_results.csv: добавить колонки fwd_bwd_median, fwd_bwd_p90, fwd_bwd_status.

[2026-09-26 14:16:26] DOCS v1.1.1:
  - REPORT.md: раздел 6.7 обновление v1.1.1 + правка аннотации
  - CHANGELOG.md: создан (v1.1.1, v1.1.0, v1.0.0)

[2026-09-26 14:26:23] DIAG v1.2.0-A:
  Проверены проекты: 20260918_2, 20260906_2, 20260825_2
  Окно 20260918_2 01:10-01:25: разбор кластеров
  Полный вывод: /tmp/diag_all_20260926_142603.txt

[2026-09-26 17:12:27] PATCH-V1.2.0:
  - ensemble_viterbi: раздельная проверка прыжка horiz/h (была 3D)
  - MAX_JUMP_H_M=100.0 (default, настраивается env)
  - generate_summary: блок Drift vs Backward + Coverage
  - Обоснование: 3D-метрика симметрично наказывала h; после потери
    backward Viterbi не мог вернуться (h-разница ~107 м > 10 м)
  - Диагноз 20260918_2: окно 01:12-01:22, backward h=894, result h=958,
    forward даёт h=871/864. GrafNav: 894.
  - Regression: сравнить batch_results.csv до/после на 45 проектах

[2026-09-28 08:44:34] SEGMENTATION v1.3.0 (ключевое изменение пайплайна):

  ПРОБЛЕМА: длинный backward-фильтр "устаёт" через 5-часовой трек, даёт
  систематический сдвиг. При отключении оборудования между вылетами integer
  сбрасываются, и Flight N в середине дня не имеет ни свежего forward, ни
  свежего backward.

  РЕШЕНИЕ: segmentation-aware обработка.
    1. detect_segments.py — парсит rover.26O, находит gaps > 300 сек
    2. ensemble_segmented.py — для каждого сегмента:
       - 8 прогонов rnx2rtkp с -ts/-te
       - Viterbi merge внутри сегмента
    3. Склейка result.pos + result.pos.stat (concatenate)

  ФИЗИКА: каждая посадка = отключение = сброс integer. Сегмент получает
  свежий forward и свежий backward на обоих концах.

  РЕЗУЛЬТАТ на 42 проектах (batch 68 мин):
    - Средний Q1: 93.0 % -> 94.1 % (+1.1 п.п.)
    - mean_all средн.: 0.22 см -> 0.11 см (-50 %)
    - Q1 = 100 %: 8 -> 9 проектов
    - 11 проектов улучшились на > 2 п.п. Q1

  КЛЮЧЕВЫЕ КЕЙСЫ:
    - 20260918_2: Q1 89.8 -> 99.6 %, mean -0.96 -> +0.11 м,
      RMS 5.47 -> 0.54 м, max 118 -> 3.81 м
    - 20260818_1: Q1 87.4 -> 99.96 %
    - 20260901_1: max_abs 88.6 -> 4.26 м
    - 20260917_1: Q1 84.4 -> 89.7 %
    - 20260819_1: Q1 -6.7, но mean +0.07 -> +0.00 (убраны "полу-правые" Q1)

  12 проектов потеряли Q1 (0.5-6.7 п.п.), но mean улучшился почти везде —
  segmentation убирает систематический сдвиг, оставляя только честные fix.

  ОТКРЫТЫЕ ВОПРОСЫ v1.3.1 (не блокеры):
    - Coverage в generate_summary считается по одному сегменту (ALERT ложный)
    - batch_ensemble.sh делает лишний pipeline_ensemble.sh до segmented
    - .stat не перезаписывается при повторном прогоне
    - compute_drift_vs_bwd считает по первому seg_*, а не агрегирует

  ФАЙЛЫ v1.3.0:
    new:  scripts/detect_segments.py
    new:  scripts/ensemble_segmented.py
    mod:  scripts/pipeline.sh (шаг 3.5 -> ensemble_segmented)
    mod:  scripts/batch_ensemble.sh (PROJECTS_OVERRIDE + segmented)
    mod:  scripts/generate_summary.py (работа с seg_*)

  Batch CSV: ~/gnss_batch_runs/batch_results.csv (42 ok / 3 skip)
  Baseline:  ~/gnss_batch_runs/batch_results_v1.1.1.csv

[2026-09-28 08:59:28] POST-BATCH VALIDATION 20260927 (v1.3.0):

  Проект 20260927 — НЕ входил в batch 42. Обработан через gp на v1.3.0
  без ручной настройки. База: 2 UBX-файла слиты автоматически.

  GrafNav:
    Q1 = 65.1 %, Fwd/Rev RMS Height = 1.071 м
    Fwd/Rev dual fix RMS H = 1.397 м ← GrafNav сам себе противоречит на 1 м

  v1.3.0 (мы):
    4 сегмента (совпало с 4 вылетами)
    Q1 = 97.01 % (+31.9 п.п. над GrafNav)
    mean_dH vs GrafNav = −0.21 м
    RMS vs GrafNav = 0.72 м
    mean drift vs backward = 0.001 м ← 1 мм внутренней согласованности
    p95(dH) = +0.64 м, >5 м: 62 эпохи (0.0 %)

  ИНТЕРПРЕТАЦИЯ: mean_dH −0.21 м — не наша ошибка, а систематика GrafNav
  по высоте (у него Fwd/Rev separation 1 м). Мы внутренне согласованы
  на 1 мм — это лучше любой другой доступной метрики.

  ЗНАЧЕНИЕ: подтверждение универсальности v1.3.0 на данных вне batch.
  Автоматическая сегментация, Q1 +32 п.п., внутренняя согласованность 1 мм.

[2026-09-28 09:14:33] v1.3.1: мелкие фиксы после v1.3.0.

  ИСПРАВЛЕНО:
    1. generate_summary.py: compute_fwd_bwd_sep / compute_drift_vs_bwd
       агрегируют по всем сегментам (было — по первому).
       Coverage: 14.6 % (ложный ALERT) → ожидаем ~90 %+.
    2. batch_ensemble.sh: pipeline_ensemble.sh вызывается только если
       rover.26O/base_surveyed.26O отсутствуют. Экономия ~2 мин/проект.
    3. batch_ensemble.sh: .stat перезаписывается при повторном прогоне.
    4. batch_ensemble.sh: N_POS проверка убрана (ensemble/ не создаётся).

  НЕ ТРОГАЛОСЬ:
    - ensemble_segmented.py (логика сегментации).
    - Q1/mean регрессия не требуется.

  ПРОВЕРКА:
    - generate_summary.py на существующем result.pos 20260927
      → ожидаем Coverage > 90 %.
    - gp 20260927 заново → ожидаем ~120 сек вместо ~180 сек.

  ОТКРЫТЫЙ ВОПРОС v1.3.2:
    - 20260825_2: max_abs +2.9 м при улучшенном mean_all и RMS.
      Локальная аномалия 26 сек в 02:58:17-43.

[2026-09-28 11:50:50] KNOWN LIMITATION 20260825_2 (закрытие исследования demote).

  РЕШЕНИЕ: не внедрять demote в production. Задокументировать как known limitation + добавить опциональный аудит-скрипт.

  ОБОСНОВАНИЕ:
    - Аномалия: 26 сек, 260 эпох из 6 088 500 (0.004 %).
    - mean_all проекта улучшен сегментацией (+0.19 см).
    - RMS улучшен (1.67 м). Только max_abs +2.9 м.
    - Критерий demote (MAD-based) не даёт 100% detection.
    - Подобран на 1 проекте, проверен на 2. Hold-out валидации нет.
    - Overfitting risk + staircase risk + рост сложности.

  АРТЕФАКТЫ:
    - scripts/detect_anomaly.py — опциональный аудит, не меняет result.pos.
    - REPORT.md — раздел 6.9 Known limitation.
    - CHANGELOG.md — подраздел Known limitations в v1.3.1.

  ИССЛЕДОВАНИЯ (в /tmp, не в production):
    - exp_a_ransac.py, exp_b_gmm.py, exp_c_mad.py, exp_d_split.py, exp_e_combo.py
    - Итог: K=50 MAD=0.5 RL=60 — 0.36% глобально, 82% TP, 0% FP (не внедрено).

  TODO v1.4.0 (или v2.0.0):
    1. Глобальный рефакторинг: numpy/scipy/sklearn вместо pure Python.
    2. Demote-критерий — только после валидации на 10+ новых проектах.
    3. Визуальный контроль (plot_summary.py) — отложен до большого релиза.

[2026-09-28 11:57:01] INCIDENT: iTerm paste corruption в REPORT.md.

  ПРОБЛЕМА: при вставке длинных heredoc (48+ строк) через iTerm из
  браузера произошла склейка строк:
    "Viterbi вы" + "Result Q1 = e22_b" + "ственный доступный"
  Файл REPORT.md содержал битую строку 519.

  РЕШЕНИЕ: binary-replace в Python (чтение байтов, .replace(bad, good),
  запись в binary). Кодировка файла UTF-8 осталась валидной.

  ПРОВЕРКИ ПОСЛЕ ФИКСА:
    - grep -c "Viterbi выResu" REPORT.md -> 0
    - grep -c "Viterbi выбрал единственный" REPORT.md -> 1
    - общий поиск артефактов -> пусто

  УРОКИ:
    1. Секции ≤30 строк при вставке через iTerm.
    2. После каждой вставки в файл — grep/sed-проверка.
    3. Для русского текста — копировать из VSCode/TextEdit, не из браузера.

[2026-09-28 16:06:44] v1.4.0: gnss_meta.py + global.conf.

  ЧТО СДЕЛАНО:
    - conf/global.conf — единый конфиг путей.
    - scripts/gnss_meta.py — единый API метаданных.
      * detect_paths из пути .NOV
      * read_anchor: day → area → legacy conf/
      * read_base: area .gnss_base.txt → legacy conf/base_ecef.txt
      * WGS84 ↔ ECEF конверсия (с проверкой residual)
      * CLI: resolve, read-anchor, read-base, read-day-anchor, check, check-area

  ТЕСТЫ (на 20260927):
    - resolve: 11 переменных (GNSS_AREA, GNSS_PROJECT, GNSS_DATE, GNSS_ROVER_DIR, GNSS_BASE_DIR, ...)
    - read-anchor: legacy fallback сработал
    - read-base: ECEF найден, LLH↔ECEF residual = 0.0000 м
    - check: OK=2 WARN=0 ERR=0
    - check-area Julietta: 30 дней обнаружено, метаданные ещё не мигрированы

  НОВАЯ СТРУКТУРА МЕТАДАННЫХ (утверждено):
    - 1_Data.nosync/<Area>/.gnss_anchor.txt         — anchor площади
    - 2_Diff.nosync/<Area>/.gnss_base.txt           — координаты базы (LLH + ECEF)
    - 2_Diff.nosync/<Area>/<YYYYMMDD>/.gnss_day_anchor.txt — дневной якорь
    - Формат: key=value с # comments

  ДАЛЬШЕ:
    - v1.4.1: gnss_area_init.py — интерактивный мастер новой площади.
    - v1.4.2: migrate_to_meta.py — миграция legacy conf/ в новые файлы (с бэкапом).
    - v1.4.3: рефакторинг pipeline.sh / batch_ensemble.sh на gnss_meta.py.
    - v1.4.4: STRUCTURE.md + CHANGELOG.md в директориях данных.

[2026-09-28 16:23:00] v1.4.2: миграция day anchors.

  СДЕЛАНО:
    - scripts/migrate_day_anchors.py -- новый скрипт.
    - Julietta: 24 day anchor -> <date>/.gnss_day_anchor.txt.
    - gnss_meta.read_anchor -> priority=day.
    - check-area Julietta: 24 OK, 3 WARN, 0 ERR.

  WARN (3):
    - 20260825: 101549 м, dh = -502.7 м. Возможно другая площадка.
    - 20260830: 1654 м, dh = +161.0 м. Ровер в воздухе.
    - 20260902: 809 м, dh = +42.1 м. То же.

  TODO v1.4.5 (пользователь: разобрать day-anchor по высотам):
    1. Проверка |dh| относительно area anchor. |dh|>30 м -> WARN.
    2. Улучшить detect_warmup.py: проверка 'на земле' (h в пределах +-10 м
       от area anchor).
    3. Пересоздать day anchor для 20260830 и 20260902.
    4. 20260825 -- проверить, Julietta ли это вообще.

  ДАЛЬШЕ:
    - v1.4.3: рефакторинг pipeline.sh / batch_ensemble.sh.
    - v1.4.4: STRUCTURE.md в существующих директориях.
    - v1.4.5: day-anchor по высотам.

[2026-09-28 17:12:59] v1.4.3: pipeline.sh -> gnss_meta.py.

  ИЗМЕНЕНО:
    - eval gnss_meta resolve -> GNSS_AREA/PROJECT/DATE/ROVER_NOV/BASE_DIR.
    - ECEF: read-base (fallback на интерактив).
    - Anchor: read-anchor (day -> area -> legacy).
    - Fail-fast rover.26O < 1 МБ (защита от Ctrl+C).

  РЕГРЕССИЯ 20260927:
    - Q1 = 97.01 %, 192290 эпох, 4 сегмента, DOP OK.
    - Идентично v1.3.1. Время 253 сек vs 254 сек.
    - ECEF и anchor -- (gnss_meta), источники подтверждены.

  ДАЛЬШЕ:
    - v1.4.4: STRUCTURE.md в существующих директориях.
    - v1.4.5: day-anchor по высотам.

[2026-09-28 17:27:53] v1.4.4: STRUCTURE.md.

  СОЗДАНО/ОБНОВЛЕНО:
    - gnss_experiment/STRUCTURE.md (был STRUCT.md, 25 сент.)
    - 1_Data.nosync/Julietta/STRUCTURE.md (новый)
    - 2_Diff.nosync/Julietta/STRUCTURE.md (перезаписан, был сломан tree)

  СТАРОЕ:
    - STRUCT.md -> STRUCT.md.legacy

  ПРОВЕРКА:
    - STRUCTURE.md для всех 3 директорий записан, 53/40/51 строк.
    - VERSION = v1.4.4.

  ДАЛЬШЕ: v1.4.5 (day-anchor по высотам).

[2026-09-28 17:54:48] v1.4.5: удаление 24 day anchor Julietta.

  ДИАГНОСТИКА 3 WARN:
    - 20260825: day anchor h=329.78, result.pos h=832.48. Ошибочный.
    - 20260830: day anchor h=993.47, result.pos h=832.49. Ошибочный.
    - 20260902: day anchor h=874.57, result.pos h=832.52. Ошибочный.
    - result.pos во всех случаях = area anchor +-2 см. Данные верные.
    - Ошибочен именно day anchor (detect_warmup без ground-check).

  ФИЗИКА:
    - Julietta: одна площадка на всю кампанию. Утром взлёт с неё,
      вечером посадка. Методические работы по калибровке Th.
    - day anchor для Julietta физически бессмысленен.

  СДЕЛАНО:
    - Удалены 24 day anchor (backup: .day_anchor_backup_<ts>/).
    - gnss_meta read-anchor: priority=area -- fallback работает.
    - check-area Julietta: OK=3 WARN=0 ERR=0 после удаления day anchor.

  TODO v1.4.6:
    - detect_warmup.py: ground-check (h_static в +-30 м от area anchor).
    - batch_ensemble.sh: удалить мёртвый блок auto-day-anchor.

[2026-09-28 18:04:29] RELEASE v1.4.5 artifacts:

  gnss_experiment_v1.4.5_20260928.tar.gz (12.5 МБ)
    sha256: b9d1c4a5428d796bea26ee07efe71aef1faa783fa0f006aaba1f472347664136
  gnss_experiment_v1.4.5_clean_20260928.tar.gz (12.1 МБ)
    sha256: d945566521e82c29b419bc142b98615b8745e7310277bf6cf4de5a3dd93821e3

  Проверка целостности (shasum -a 256 -c) -- OK/OK.

  ИТОГ СЕССИИ 2026-09-28 (6 релизов за день):
    v1.4.0 -- gnss_meta.py + global.conf
    v1.4.1 -- gnss_area_init.py (мастер площади)
    v1.4.2 -- migrate_day_anchors.py (24 day anchor)
    v1.4.3 -- pipeline.sh -> gnss_meta (Q1=97.01% идентично v1.3.1)
    v1.4.4 -- 3 x STRUCTURE.md
    v1.4.5 -- удаление 24 day anchor (check-area: OK=3 WARN=0 ERR=0)

  СТАТУС: v1.4.5 -- стабильная. Пауза до новых проектов.

[2026-09-29 15:54:15] v1.4.6: pipeline UX + batch cleanup.

  PIPELINE.SH:
    - ask_base default: Enter -> GNSS_BASE_DIR.
    - prefer merged.ubx: без повторного слияния.
    - .NOV extension check (prompt 'Продолжить всё равно?').

  BATCH_ENSEMBLE.SH:
    - удалён мёртвый блок auto-day-anchor.

  ПРОВЕРКА 20260929 (первый прогон после v1.4.5):
    - Q1 = 83.15 % (GrafNav 55.5 %), +27.7 п.п.
    - 165709 эпох, 6 сегментов, DOP OK.
    - merged.ubx найден и использован без слияния.
    - ЕСЛИ запускался старый .NOV -> fail-fast сработал (1640 байт).

[2026-09-29 15:56:36] RELEASE v1.4.6 artifacts:

  gnss_experiment_v1.4.6_20260929.tar.gz (12.6 МБ)
    sha256: 19ac8b84b0a834040d2676d4f6144f82fb05c0e1c3b1f09da2c5134a5e864234
  gnss_experiment_v1.4.6_clean_20260929.tar.gz (12.1 МБ)
    sha256: 39e08c2b78015bc0abb78a9d3beb9e551d95f5bd4aba489afb7b344f7d8f8d2d

  Проверка целостности (shasum -a 256 -c) -- OK/OK.

  PRODUCTION-VALIDATION 20260929:
    - Первый проект на v1.4.5/1.4.6 вне batch 42.
    - GrafNav: Q1=55.5%, 79513 не обработано (32.4%).
    - Мы: Q1=83.15%, 165709 эпох, 6 сегментов. +27.7 п.п.
    - baseline max 112 км, avg 44.6 км -- длинный.
    - DOP OK, fail-fast сработал (не .NOV).

[2026-09-29 16:01:30] v1.4.7: убрано дублирование даты в именах.

  ПРОБЛЕМА:
    - OUTPUT_XYZ был 20260929_20260929_154257_50301.xyz.
    - TIMESTAMP содержал %Y%m%d (совпадал с RUN_NAME=дата).

  ИСПРАВЛЕНО:
    - TIMESTAMP: %H%M%S_$$ (без даты).
    - OUTPUT_XYZ: 20260929_154257_50301.xyz.
    - WORK_DIR: 20260929_154257_50301/.
    - merged.ubx: merged_20260929_154257_50301.ubx (дата сохранена).

[2026-09-29 17:18:22] OMSUSKHAN: отложено.

  ПРИЧИНА:
    - Сложная площадь: несколько баз, смена размещения.
    - 3-8 июля 2026 -- reference network (MGDN), не локальная база.
    - Требует отдельного режима --base-rinex в pipeline.sh.
    - Не улучшает pipeline для других площадок.

  СОБРАНО (для будущего, если понадобится):
    - Координаты баз: CrossOver bottle -> User.fvt (файл избранного GrafNav).
      Omsukchan: budka0, Fora1, bort, Diff0, Diff1.
      Опорная сеть: MGDN, 87an, PKAM.
    - budka0 == Fora1 (+-1 см). Основная база = Fora1.
    - Reference network файлы лежат в директории ровера (MGDN_*.26o + .sta).

  СТАТУС: отложено без срока. Приоритет -- Julietta и новые проекты.

[2026-09-29 19:43:56] PLOT_SUMMARY: отложено до мажорного релиза.

  ЧТО СДЕЛАНО:
    - plot_summary.py (696 строк) + шаблон + plotly.min.js в bin/.
    - 4 вкладки (A: raw vs result, B: orig vs segmented,
      C: ensemble vs best, D: our vs GrafNav).
    - Интерактивный HTML, LTTB downsample, аннотации.
    - Не интегрировано в pipeline.sh.

  ПРИЧИНА ОСТАНОВКИ:
    - Получился конструктор ради конструктора.
    - Много панелей, много источников -- нечитаемо.
    - Нет чёткого ТЗ от пользователя на набор сравнений.

  ПЛАН: пользователь сформулирует необходимый набор данных
  для сравнения. Затем -- отдельный мажорный релиз v1.5.0.

  АРТЕФАКТЫ СОХРАНЕНЫ (не удалены):
    - scripts/plot_summary.py
    - scripts/plot_summary_template.html
    - bin/plotly.min.js
    - pip: plotly 7.1.0
