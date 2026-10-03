# RTKLIB Ensemble Pipeline

GNSS post-processing pipeline for helicopter-borne aerosurvey. An open
replacement for GrafNav, built on
[RTKLIB-EX 2.5.1 (demo5)](https://github.com/rtklibexplorer/RTKLIB).

Combines **8 parallel RTKLIB runs** (elmask x direction) with a
**Viterbi-based ensemble merge**, **flight-segment detection**, and
**metadata next to raw data** (anchor, base coordinates).

## Key features

- **Segmentation-aware processing.** Automatically splits a track by long
  gaps (> 300 s) -- each flight is processed independently. Fixes the
  "tired backward filter" problem on multi-hour tracks with equipment
  shutdowns between flights.
- **8-run ensemble + Viterbi merge.** Combines forward/backward runs at
  different elevation masks (15 / 17 / 20 / 22 deg). Beats single-run
  RTKLIB on long baselines.
- **Backward preference.** On aerosurvey data with long gaps, the backward
  solution outperforms combined/forward by 15--40 pp Q1.
- **Metadata next to data.** Anchor, base coordinates, and per-day anchors
  stored in `.gnss_*.txt` files in `Documents/`, not in configs.
- **Fail-fast.** Automatic abort on bad inputs (empty RINEX, wrong file
  types, interrupted NovAtel Convert).

## Results (Julietta, 42+ projects)

| Metric | GrafNav 8.70 | This pipeline |
|---|---|---|
| Mean Q1 | 78.0 % | **94.1 %** |
| Q1 on long baselines (> 80 km) | 51--59 % | **83--99 %** |
| Mean dH (Q=1) vs GrafNav | reference | +/- 0.3 cm |

## Requirements

- **OS:** macOS (tested on macOS 26 / Apple Silicon). Linux untested.
- **Python:** 3.9+ (stdlib only; `plotly` optional for experimental
  plotting).
- **RTKLIB-EX 2.5.1 (demo5)** -- prebuilt binaries in `bin/`
  (macOS arm64).
- **NovAtel Convert** -- for `.NOV` to RINEX conversion
  (tested via CrossOver on macOS).

## Install

### 1. Clone

    git clone https://github.com/petrowmaxic/rtklib-ensemble-pipeline.git
    cd rtklib-ensemble-pipeline

### 2. Optional: rebuild RTKLIB-EX binaries

The prebuilt `bin/rnx2rtkp_EX` and `bin/convbin_EX` are for macOS arm64.
For other platforms, build from source:

    git clone https://github.com/rtklibexplorer/RTKLIB.git
    cd RTKLIB/app/consapp/rnx2rtkp/gcc
    make
    cp rnx2rtkp /path/to/rtklib-ensemble-pipeline/bin/rnx2rtkp_EX

Same for `convbin`. See `docs/APPENDIX_D_env.md` for version details.

### 3. Configure paths

Edit `conf/global.conf`:

    rover_root = ~/Documents/1_Data.nosync
    base_root  = ~/Documents/2_Diff.nosync

### 4. Optional: Python deps

    pip3 install -r requirements.txt

## Quick start

    # Single project (interactive):
    ./scripts/pipeline.sh <rover.NOV> <base.ubx | base_dir>

    # Batch:
    ./scripts/batch_ensemble.sh

Pipeline steps:

1. Convert base UBX to RINEX, patch APPROX POSITION.
2. Convert rover NOV to RINEX (NovAtel Convert).
3. Detect flight segments by gaps > 300 s.
4. Run 8 RTKLIB configs on each segment in parallel (N_JOBS=6).
5. Viterbi-merge 8 runs per segment.
6. Concatenate segments, export to Oasis Montaj XYZ.

## Directory structure

    rtklib-ensemble-pipeline/
      bin/              rnx2rtkp_EX, convbin_EX (macOS arm64)
      conf/             global.conf, FINAL.conf, STATIC.conf
      docs/             REPORT.md, JOURNAL.md, CHANGELOG.md, HOWTO_*
      scripts/          pipeline.sh, ensemble_viterbi.py, gnss_meta.py, ...
      STRUCTURE.md      full project layout

Metadata (anchors, base coordinates) lives next to raw data, not in this
repo:

    <base_root>/<Area>/.gnss_anchor.txt
    <base_root>/<Area>/.gnss_base.txt
    <base_root>/<Area>/<YYYYMMDD>/.gnss_day_anchor.txt

Managed by `scripts/gnss_meta.py` (`resolve`, `read-anchor`, `read-base`,
`check-area`).

## Documentation

- `docs/REPORT.md` -- full technical report
- `docs/JOURNAL.md` -- chronological development log
- `docs/CHANGELOG.md` -- version history
- `docs/HOWTO_ANCHOR*.md` -- anchor workflow
- `STRUCTURE.md` -- project layout

## Citation

    Petrov, M. (2026). RTKLIB Ensemble Pipeline: open replacement for
    GrafNav in helicopter-borne aerosurvey.
    https://github.com/petrowmaxic/rtklib-ensemble-pipeline

## License

BSD 2-Clause -- see [LICENSE](LICENSE). Compatible with RTKLIB-EX, which
uses the same license.

## Acknowledgments

- Tomoji Takasu -- RTKLIB
- rtklibexplorer (Tim Everett) -- RTKLIB-EX (demo5)
- NovAtel -- OEMStar / OEM7 receivers
- u-blox -- base station receivers
