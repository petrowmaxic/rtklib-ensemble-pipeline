# Протоколы измерений

## P.0. Получение anchor из прогрева ровера

Когда: после первого вылета дня (_1 или YYYYMMDD).

Команда:
    ~/gnss_experiment/scripts/make_anchor_for_day.sh 20260922_1

Результат:
- Файл conf/ANCHOR_<YYYYMMDD>.txt
- Используется всеми проектами этого дня (_2, _3...)

Проверка:
    python3 ~/gnss_experiment/scripts/detect_warmup.py \
        ~/gnss_batch_runs/20260922_1/ensemble_viterbi.pos 0.5 300

Snapshot каждые 5 минут. Ожидается: 40-60 мин статики, потом взлёт.

## P.1. Получение anchor (полная процедура)

```bash
mkdir -p ~/gnss_anchor_workspace
cd ~/gnss_anchor_workspace

# 1. База
~/gnss_experiment/bin/convbin_EX -r ubx -o base.26O -n base.26N <base.ubx>
python3 ~/gnss_experiment/scripts/patch_approx_position.py \
  base.26O -2772947.5700 1351588.2062 5564759.1253
cp base.26O base_surveyed.26O

# 2. Ровер
cp <rover.NOV> rover.NOV
WINE="/Applications/CrossOver.app/Contents/SharedSupport/CrossOver/CrossOver-Hosted Application/wine"
EXE="/Users/maxic/Library/Application Support/CrossOver/Bottles/Novatel converter/drive_c/Program Files/NovAtel Convert/NovAtelConvert.exe"
"$WINE" "$EXE" -r3.03 rover.NOV
mv rover.80O rover.26O 2>/dev/null
mv rover.80N rover.26N 2>/dev/null

# 3. Static-обработка
~/gnss_experiment/bin/rnx2rtkp_EX -k ~/gnss_experiment/conf/STATIC.conf -ti 1.0 \
  -r -2772947.5700 1351588.2062 5564759.1253 \
  -o static.pos rover.26O base_surveyed.26O rover.26N base.26N

# 4. Усреднение (центральный час)
LC_NUMERIC=C awk '!/^%/{split($2,t,":"); h=t[1]+0;
  if(h==4){n++; slat+=$3; slon+=$4; sh+=$5;
    if(mn==""||$5<mn) mn=$5; if($5>mx) mx=$5}
} END{printf "%d %.9f %.9f %.4f [%.3f..%.3f]\n",
    n, slat/n, slon/n, sh/n, mn, mx}' static.pos

# 5. Записать
echo "<lat> <lon> <h>" > ~/gnss_experiment/conf/ANCHOR_<project>.txt
## P.2. Обработка одного проекта (gp)

bash
gp
# Ровер: <path>.NOV
# База: <path>.ubx или директория
# ECEF: Enter
# Y
## P.3. Batch 41 проекта

bash
export N_JOBS=6
cd ~/gnss_experiment
~/gnss_experiment/scripts/batch_ensemble.sh 2>&1 | tee -a ~/gnss_batch_runs/batch_full.log
## P.4. Проверка результата

bash
LC_NUMERIC=C awk '!/^%/{q[$6]++} END{for(k in q) print "Q="k, q[k]+0}' result.pos
python3 ~/gnss_experiment/scripts/check_dop_100s.py <xyz>
python3 ~/gnss_experiment/scripts/compare_q1.py <our.pos> <grafnav.xyz> "label"
## P.5. Hold-out валидация (рекомендуемая)

На проекте, не участвовавшем в настройке (например, 20260916):

bash
# Default
python3 ~/gnss_experiment/scripts/ensemble_viterbi.py \
  ~/gnss_batch_runs/20260916/ensemble /tmp/holdout_default.pos
LC_NUMERIC=C awk '!/^%/{q[$6]++} END{print "Q1:", q[1]+0}' /tmp/holdout_default.pos

# MIN_AGREE=1
MIN_AGREE=1 python3 ~/gnss_experiment/scripts/ensemble_viterbi.py \
  ~/gnss_batch_runs/20260916/ensemble /tmp/holdout_min1.pos

# MIN_AGREE=3
MIN_AGREE=3 python3 ~/gnss_experiment/scripts/ensemble_viterbi.py \
  ~/gnss_batch_runs/20260916/ensemble /tmp/holdout_min3.pos

# Сравнить
for f in /tmp/holdout_*.pos; do
  echo "=== $f ==="
  LC_NUMERIC=C awk '!/^%/{q[$6]++} END{printf "Q1=%d (%.2f%%)\n", q[1]+0, 100*q[1]/NR}' "$f"
done
Интерпретация: если Q1 варьируется < 2 п.п. — параметры не overfit.

## P.6. Чувствительность к anchor (рекомендуемая)

bash
# Anchor +10 см
ANCHOR_LAT=61.161609673 \
  python3 ~/gnss_experiment/scripts/ensemble_viterbi.py \
  ~/gnss_batch_runs/20260922_1/ensemble /tmp/anchor_p10.pos

# Anchor +50 см
ANCHOR_LAT=61.161614073 \
  python3 ~/gnss_experiment/scripts/ensemble_viterbi.py \
  ~/gnss_batch_runs/20260922_1/ensemble /tmp/anchor_p50.pos

# Сравнить Q1 и mean_dH
python3 ~/gnss_experiment/scripts/compare_q1.py \
  /tmp/anchor_p10.pos \
  /Users/maxic/Documents/1_Data.nosync/Julietta/20260922_1/20260922_1.xyz \
  "anchor+10"
