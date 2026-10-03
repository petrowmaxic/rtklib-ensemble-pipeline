# Приложение D. Окружение

## D.1. Аппаратное

- MacBook Pro M-series: 10 ядер, 16 ГБ RAM
- Диск: ~20 ГБ на batch

## D.2. ОС

- macOS 26 (Darwin 25.x), Apple Silicon arm64

## D.3. ПО

| Компонент | Версия |
|---|---|
| RTKLIB-EX (demo5) | 2.5.1 |
| NovAtel Convert | 2.2 |
| CrossOver | 24.x |
| Python | 3.9+ (только stdlib) |
| GrafNav (эталон) | 8.70.5101 |

## D.4. Пути

- RTKLIB-EX: `~/RTKLIB-2.5.1/`
- Пайплайн: `~/gnss_experiment/`
- Результаты batch: `~/gnss_batch_runs/`
- Исходные данные: `~/Documents/1_Data.nosync/Julietta/`, `~/Documents/2_Diff.nosync/Julietta/`

## D.5. Точные версии (КРИТИЧНО для воспроизводимости)

| Компонент | Версия / коммит | Дата сборки | Флаги |
|---|---|---|---|
| RTKLIB-EX | demo5 2.5.1 | 2026-08-15 | `-DENAGLO -DENAGAL -DENACMP -DNFREQ=5` |
| convbin_EX | 2.5.1 | 2026-08-15 | — |
| rnx2rtkp_EX | 2.5.1 | 2026-08-15 | — |
| NovAtel Convert | 2.2 | — | — |
| CrossOver | 24.x | — | — |
| Python | 3.9+ | — | stdlib |

**УПУЩЕНИЕ:** SHA коммита RTKLIB-EX не зафиксирован. Для строгой воспроизводимости рекомендуется:

```bash
cd ~/RTKLIB-2.5.1
git rev-parse HEAD 2>/dev/null || echo "не git-репозиторий"
# записать в этот файл

## D.6. Хеши бинарников

bash
shasum ~/gnss_experiment/bin/rnx2rtkp_EX ~/gnss_experiment/bin/convbin_EX
Заполнить после проверки:

<вставить результат>
