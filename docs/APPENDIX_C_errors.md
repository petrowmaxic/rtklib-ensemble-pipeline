# Приложение C. Ошибки и решения

## C.1. Пробел после `=` в конфиге RTKLIB (КРИТИЧНО)

RTKLIB не обрезает пробелы вокруг значения.
Неправильно:

pos2-gloarmode = on → invalid option value (значение " on")
pos2-armode = fix-and-hold → invalid option value

Правильно:

pos2-gloarmode=on → OK
pos2-armode=fix-and-hold → OK

**Касается всех enum-параметров:**
- `pos1-posmode`, `pos1-soltype`, `pos1-ionoopt`, `pos1-tropopt`, `pos1-dynamics`
- `pos2-armode`, `pos2-gloarmode`, `pos2-navsys`

**Числовые параметры** (`pos2-arthres=2.5`) — пробелы допустимы.

На отладку ушло несколько часов. Все конфиги в `~/gnss_experiment/conf/` написаны правильно.

## C.2. Полная таблица

| Ошибка | Причина | Решение |
|---|---|---|
| `dyld: Library not loaded` | CMake не проставил rpath | `install_name_tool -change @rpath/librtklib.dylib /usr/local/lib/librtklib.dylib <binary>` |
| `rover.80O` вместо `rover.26O` | NovAtel не определил год | Автонормализация в `pipeline_ensemble.sh` |
| `rover.26O` пустой | temp-файлы от прошлого запуска | Автоочистка `rover.NOV_*temp_*.txt` |
| DOP missing > 50 % | Сопоставление по TOW | `export_v2.py` — по индексу эпохи |
| `awk: division by zero` | n=0 | Проверка `if(n>0)` |
| KeyError: datetime | нет t в all_pos[0] | Fallback на любой run |
| Q1 упал вдвое | Забыт `ant2-antdelu=1.800` | Проверить конфиг |
| Q1 = 60 % на backward | Нет GLONASS-фазы | NovAtel Convert вместо convbin |
| `invalid option value` | Пробел после `=` | Убрать пробелы |
| Viterbi пишет только последний сегмент | Backtracking break | Segment-aware backtracking |
| Anchor fallback даёт 400+ м | Ровер далеко от базы | Fallback на float лучшего run |
| `min_votes=2` ломает 20260921_2 | Теряются одиночные кластеры | Quality-weighted votes |
| Union fwd∪rev mean +21 см | Ложные fix без проверки | Viterbi + anchor |
