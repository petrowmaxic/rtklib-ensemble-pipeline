# Как получить и настроить anchor

**Anchor** — координата площадки взлёта/посадки. В пайплайне используется как **tie-breaker между кластерами Viterbi** (см. REPORT.md раздел 2.4). Не обязателен — если его нет, pipeline работает на общем `ANCHOR_Julietta.txt`.

## 1. Когда anchor нужен

- **Всегда** — pipeline использует его по умолчанию
- **Приоритет поиска:** project-specific > day-level > Julietta
- **Автоматически** — для `_1` и `YYYYMMDD` (первый вылет дня) pipeline сам его считает

## 2. Откуда anchor берётся

**Основной источник:** статичный прогрев ровера в начале дня.

- Вертолёт прогревается 40–60 минут перед первым вылетом
- Логгер ровера всё это время пишет на 10 Гц
- Static-обработка даёт координату площадки с точностью ±1 см

**Проверка наличия прогрева:** `detect_warmup.py` (см. раздел 3).

## 3. Автоматическое получение

**Для первого вылета дня** (имя `YYYYMMDD` или `YYYYMMDD_1`):

```bash
# 1. Обычный запуск gp или batch
gp

# 2. После обработки — извлечь anchor
~/gnss_experiment/scripts/make_anchor_for_day.sh 20260922_1

# 3. Проверить
cat ~/gnss_experiment/conf/ANCHOR_20260922.txt
Скрипт make_anchor_for_day.sh:

Ищет статику в ~/gnss_batch_runs/<project>/ensemble_viterbi.pos
Фильтр: скорость < 0.5 м/с, длительность ≥ 300 сек
Усредняет координаты центрального периода
Сохраняет в conf/ANCHOR_<YYYYMMDD>.txt
Проверка статики вручную:

bash
python3 ~/gnss_experiment/scripts/detect_warmup.py \
    ~/gnss_batch_runs/20260922_1/ensemble_viterbi.pos 0.5 300
Вывод: snapshot каждые 5 минут + найденный статичный период + строка ANCHOR:.

Для _2, _3...: автоматически используется ANCHOR_<date>.txt того же дня.

4. Ручное получение (из отдельной статичной стоянки)

Идеальный вариант — специальная стоянка (как 20260823_cTo9Nka, 3.5 часа).

bash
mkdir -p ~/gnss_anchor_workspace && cd ~/gnss_anchor_workspace

# 1. База UBX -> RINEX
~/gnss_experiment/bin/convbin_EX -r ubx -o base.26O -n base.26N <base.ubx>
python3 ~/gnss_experiment/scripts/patch_approx_position.py \
    base.26O -2772947.5700 1351588.2062 5564759.1253
cp base.26O base_surveyed.26O

# 2. Ровер NOV -> RINEX
cp /path/<progrev>.NOV rover.NOV
WINE="/Applications/CrossOver.app/Contents/SharedSupport/CrossOver/CrossOver-Hosted Application/wine"
EXE="/Users/maxic/Library/Application Support/CrossOver/Bottles/Novatel converter/drive_c/Program Files/NovAtel Convert/NovAtelConvert.exe"
"$WINE" "$EXE" -r3.03 rover.NOV
[ -f rover.80O ] && mv rover.80O rover.26O
[ -f rover.80N ] && mv rover.80N rover.26N

# 3. Static-обработка
~/gnss_experiment/bin/rnx2rtkp_EX -k ~/gnss_experiment/conf/STATIC.conf -ti 1.0 \
    -r -2772947.5700 1351588.2062 5564759.1253 \
    -o static.pos rover.26O base_surveyed.26O rover.26N base.26N

# 4. Усреднить центральный час
LC_NUMERIC=C awk '!/^%/{split($2,t,":"); h=t[1]+0;
  if(h==4){n++; slat+=$3; slon+=$4; sh+=$5}} END{
    printf "%.9f %.9f %.4f\n", slat/n, slon/n, sh/n}' static.pos
5. Валидация anchor

Против GrafNav-эталона: расхождение < 5 см
Против других anchors Julietta: все в радиусе ~10 м
Текущие anchors Julietta (2026-09-26):

День	lat	lon	h
20260818	61.161569	154.015052	832.443
20260819	61.161606	154.015085	832.435
20260821	61.161611	154.015089	832.442
20260826	61.161608	154.015106	832.468
20260831	61.161614	154.015109	832.464
20260901	61.161610	154.015109	832.468
20260906	61.161611	154.015111	832.478
20260914	61.161615	154.015114	832.484
20260917	61.161615	154.015111	832.466
20260918	61.161618	154.015116	832.470
20260920	61.161622	154.015123	832.490
20260921	61.161611	154.015110	832.476
20260922	61.161617	154.015110	832.463
Julietta	61.161610	154.015099	832.461
Разброс между днями: ~10 м lat/lon, 6 см h.

6. Логика приоритета

text
RUN_NAME = basename(dirname(rover.NOV))
ANCHOR_DATE = RUN_NAME[:8]

if $HOME/gnss_experiment/conf/ANCHOR_<RUN_NAME>.txt:
    use project-specific
elif $HOME/gnss_experiment/conf/ANCHOR_<ANCHOR_DATE>.txt:
    use day-level
elif $HOME/gnss_experiment/conf/ANCHOR_Julietta.txt:
    use Julietta-level
else:
    anchor = (0,0,0) → работает без anchor
7. Частые ошибки

Симптом	Причина	Решение
ANCHOR_<date>.txt пустой	detect_warmup не нашёл статику	Проверить вручную detect_warmup.py
Q1 сильно упал	Anchor с ошибкой > 100 м	Удалить, использовать ANCHOR_Julietta.txt
Файл с CR (\r)	Скопирован с Windows	dos2unix conf/ANCHOR_*.txt
Все anchors разные по 100 м	Съёмка с разных площадок	Разделить проекты по регионам
~ не разворачивается	[ -f "~/path" ]	Использовать $HOME/path
8. Формат файла

text
61.161609573 154.015098774 832.4611
Одна строка
Три числа через пробел
Десятичные градусы (не DMS)
LF в конце
Без комментариев
text

---

## D. Патч REPORT.md — исправление backticks (проверка)

```bash
grep -n "см\.  и \|см\. \`detect_warmup" ~/gnss_experiment/docs/REPORT.md
Если строка ещё с пустыми местами — применить патч:

bash
python3 -c "
from pathlib import Path
P = Path.home() / 'gnss_experiment/docs/REPORT.md'
text = P.read_text()
import re
# Найти строку с двумя подряд пробелами и точкой в конце (признак съеденных backticks)
old = 'Автоматически получается из статики (40–50 мин прогрева ровера, см.  и ).'
new = 'Автоматически получается из статики (40–50 мин прогрева ровера) скриптами detect_warmup.py и make_anchor_for_day.sh.'
if old in text:
    P.write_text(text.replace(old, new, 1))
    print('✓ backticks восстановлены')
elif new in text:
    print('· уже восстановлено')
else:
    print('✗ строка не найдена — пришли grep -n \"Автоматически получается\" REPORT.md')
"