#!/usr/bin/env python3
"""ensemble_segmented.py <WORK_DIR>
Сегментная обработка: detect → 8 rnx2rtkp per segment → Viterbi per segment → merge.
Требует env: BASE_ECEF, ANCHOR_LAT, ANCHOR_LON, ANCHOR_H.
Выход: <WORK_DIR>/result.pos
"""
import os, sys, subprocess, time
from concurrent.futures import ThreadPoolExecutor, as_completed

EXP = os.path.expanduser("~/gnss_experiment")
BIN_RNX = os.path.join(EXP, "bin", "rnx2rtkp_EX")
CONF    = os.path.join(EXP, "conf", "FINAL.conf")
DETECT  = os.path.join(EXP, "scripts", "detect_segments.py")
VITERBI = os.path.join(EXP, "scripts", "ensemble_viterbi.py")

N_JOBS   = int(os.environ.get("N_JOBS", "6"))
ECEF     = os.environ.get("BASE_ECEF", "")
GAP      = os.environ.get("SEG_GAP_SEC", "300")
MIN_SEG  = os.environ.get("SEG_MIN_SEC", "300")

if len(sys.argv) < 2:
    print("usage: ensemble_segmented.py <WORK_DIR>", file=sys.stderr)
    sys.exit(1)

WORK = sys.argv[1]
ROVER = os.path.join(WORK, "rover.26O")
BASE  = os.path.join(WORK, "base_surveyed.26O")
NAV_R = os.path.join(WORK, "rover.26N")
NAV_B = os.path.join(WORK, "base.26N")
LOGS  = os.path.join(WORK, "logs")
os.makedirs(LOGS, exist_ok=True)

for p in [ROVER, BASE, NAV_R, NAV_B]:
    if not os.path.exists(p):
        print(f"ERROR: нет {p}", file=sys.stderr)
        sys.exit(1)

# 1. Detect segments
r = subprocess.run(["python3", DETECT, ROVER, GAP, MIN_SEG],
                   capture_output=True, text=True)
if r.returncode != 0:
    print(f"ERROR: detect_segments.py rc={r.returncode}: {r.stderr}",
          file=sys.stderr)
    sys.exit(1)

segments = []
for line in r.stdout.splitlines():
    line = line.strip()
    if not line or line.startswith("#"):
        continue
    a, b = line.split("|")
    segments.append((a, b))

print(f"  Сегментов: {len(segments)}")
for i, (a, b) in enumerate(segments, 1):
    print(f"    {i}: {a} -> {b}")
sys.stderr.write(r.stderr)

if not segments:
    print("ERROR: нет сегментов", file=sys.stderr)
    sys.exit(1)

# 2. Prepare segment dirs
seg_dirs = []
for i, (t_start, t_end) in enumerate(segments, 1):
    work = os.path.join(WORK, f"seg_{i}")
    os.makedirs(work, exist_ok=True)
    seg_dirs.append((work, t_start, t_end))


def run_one(work, t_start, t_end, el, st):
    out = os.path.join(work, f"e{el}_{st}.pos")
    if os.path.exists(out) and os.path.getsize(out) > 5000:
        return ("skip", el, st)
    conf_tmp = os.path.join(work, f"e{el}_{st}.conf")
    with open(CONF) as f:
        conf = f.read()
    conf = conf.replace("pos1-elmask        =17",
                        f"pos1-elmask        ={el}")
    conf = conf.replace("pos1-soltype        =backward",
                        f"pos1-soltype        ={st}")
    with open(conf_tmp, "w") as f:
        f.write(conf)
    ds, ts = t_start.split(" ")
    de, te = t_end.split(" ")
    cmd = [BIN_RNX, "-k", conf_tmp,
           "-ts", ds, ts, "-te", de, te,
           "-ti", "0.10"]
    if ECEF:
        cmd += ["-r"] + ECEF.split()
    cmd += ["-o", out, ROVER, BASE, NAV_R, NAV_B]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
        return ("ok" if r.returncode == 0 else f"rc={r.returncode}", el, st)
    except subprocess.TimeoutExpired:
        return ("timeout", el, st)


seg_outputs = []
t_all = time.time()
for i, (work, t_start, t_end) in enumerate(seg_dirs, 1):
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=N_JOBS) as ex:
        futs = [ex.submit(run_one, work, t_start, t_end, el, st)
                for el in [15, 17, 20, 22]
                for st in ["forward", "backward"]]
        results = [f.result() for f in as_completed(futs)]
    n_ok = sum(1 for s, _, _ in results if s in ("ok", "skip"))
    dt = time.time() - t0
    print(f"  Сегмент {i}: rnx2rtkp {n_ok}/8 ok за {dt:.0f} сек")
    viterbi_out = os.path.join(work, "viterbi.pos")
    vlog = os.path.join(work, "viterbi.log")
    with open(vlog, "w") as lf:
        subprocess.run(["python3", VITERBI, work, viterbi_out],
                       stdout=lf, stderr=subprocess.STDOUT)
    if not os.path.exists(viterbi_out):
        print(f"  ERROR: Viterbi не создал {viterbi_out}", file=sys.stderr)
        sys.exit(1)
    seg_outputs.append(viterbi_out)

# 3. Merge
result = os.path.join(WORK, "result.pos")
first = True
n_written = 0
with open(result, "w") as fout:
    for p in seg_outputs:
        with open(p) as f:
            for line in f:
                if line.startswith("%"):
                    if first:
                        fout.write(line)
                else:
                    fout.write(line)
                    n_written += 1
        first = False

print(f"  Склейка: {n_written} эпох -> {result}")

# 4. result.pos.stat — склейка .stat от всех сегментов
# ВАЖНО: export_v2 матчит .pos[i] к .stat[i] по позиции, поэтому .stat
# должен содержать столько же эпох и в том же порядке, что и result.pos.
stat_candidates = [
    "e15_backward.pos.stat",
    "e17_backward.pos.stat",
    "e15_forward.pos.stat",
    "e22_backward.pos.stat",
]
stat_out = os.path.join(WORK, "result.pos.stat")
if os.path.lexists(stat_out):
    os.remove(stat_out)

n_stat_total = 0
header_written = False
with open(stat_out, "w") as fout:
    for seg_work, _, _ in seg_dirs:
        stat_src = None
        for cand in stat_candidates:
            p = os.path.join(seg_work, cand)
            if os.path.exists(p) and os.path.getsize(p) > 1000:
                stat_src = p
                break
        if not stat_src:
            print(f"  WARN: нет .stat для {seg_work}")
            continue
        with open(stat_src) as f:
            for line in f:
                if line.startswith("%"):
                    if not header_written:
                        fout.write(line)
                else:
                    fout.write(line)
                    n_stat_total += 1
        header_written = True

print(f"  result.pos.stat: {n_stat_total} эпох (склейка {len(seg_dirs)} сегментов)")

print(f"  Итого: {time.time() - t_all:.0f} сек")
