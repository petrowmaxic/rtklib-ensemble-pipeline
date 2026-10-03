#!/usr/bin/env python3
"""migrate_day_anchors.py — миграция day-anchor из conf/ в новую структуру (v1.4.2).

Читает conf/ANCHOR_<YYYYMMDD>.txt, создаёт
    <base_root>/<Area>/<YYYYMMDD>/.gnss_day_anchor.txt

Опции:
    --area Julietta        # если задано, обрабатывает только эту площадь
    --dry-run              # показать, что будет сделано, без записи
    --force                # перезаписать существующие .gnss_day_anchor.txt
    --mark-migrated        # переименовать conf/ANCHOR_<date>.txt в .migrated
    --no-backup            # не создавать бэкапы (по умолчанию — создаются)
"""
import os, sys, re, shutil, argparse
from pathlib import Path
from datetime import datetime

EXP = os.path.expanduser("~/gnss_experiment")
sys.path.insert(0, os.path.join(EXP, "scripts"))
from gnss_meta import (load_global_conf, META_DAY,
                       wgs84_to_ecef, read_kv)

DATE_RE = re.compile(r'^ANCHOR_(\d{8})\.txt$')

def scan_legacy_day_anchors(conf_dir):
    """Возвращает список (date_str, path) для ANCHOR_<YYYYMMDD>.txt."""
    out = []
    for f in sorted(os.listdir(conf_dir)):
        m = DATE_RE.match(f)
        if m:
            out.append((m.group(1), os.path.join(conf_dir, f)))
    return out

def parse_legacy_anchor(path):
    """conf/ANCHOR_<date>.txt: 'lat lon h' одной строкой.
    Возвращает dict или None."""
    try:
        with open(path) as f:
            line = f.readline().strip()
    except OSError:
        return None
    parts = line.split()
    if len(parts) < 3:
        return None
    try:
        lat, lon, h = float(parts[0]), float(parts[1]), float(parts[2])
    except ValueError:
        return None
    return {'lat': lat, 'lon': lon, 'h': h}

def write_day_anchor(path, anchor, date_str, source_file, no_backup):
    """Записывает .gnss_day_anchor.txt в key=value формате."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    bak = None
    if p.exists() and not no_backup:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        bak = p.parent / (p.name + f".bak_{ts}")
        shutil.copy2(p, bak)
    lines = [
        f"# GNSS Day Anchor — {date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}",
        f"# Создано: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"# Source: migrated from {source_file}",
        "# Формат: key=value, # comments (см. gnss_meta.py)",
        "",
        f"lat = {anchor['lat']:.9f}",
        f"lon = {anchor['lon']:.9f}",
        f"h = {anchor['h']:.4f}",
        "source = migrated_from_conf",
        "",
    ]
    with open(p, "w") as f:
        f.write("\n".join(lines))
    return str(p), (str(bak) if bak else None)

def main():
    ap = argparse.ArgumentParser(
        description="Миграция day-anchor conf/ANCHOR_<date>.txt -> "
                    "<base_root>/<Area>/<date>/.gnss_day_anchor.txt")
    ap.add_argument('--area', type=str, help='Только эта площадь (иначе все)')
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--force', action='store_true',
                    help='Перезаписать существующие .gnss_day_anchor.txt')
    ap.add_argument('--mark-migrated', action='store_true',
                    help='Переименовать conf/ANCHOR_<date>.txt в .migrated')
    ap.add_argument('--no-backup', action='store_true')
    args = ap.parse_args()

    conf = load_global_conf()
    base_root = Path(conf["base_root"])
    conf_dir = os.path.join(conf["gnss_experiment"], "conf")

    print("=" * 70)
    print("  Migrate Day Anchors (v1.4.2)")
    print("=" * 70)
    print(f"  conf_dir:  {conf_dir}")
    print(f"  base_root: {base_root}")
    if args.area:
        print(f"  area:      {args.area}")
    else:
        print(f"  area:      ВСЕ")
    print(f"  dry-run:   {args.dry_run}")
    print(f"  force:     {args.force}")
    print()

    legacy = scan_legacy_day_anchors(conf_dir)
    print(f"Найдено legacy ANCHOR_<date>.txt: {len(legacy)}")
    if not legacy:
        print("Нечего мигрировать.")
        sys.exit(0)

    # Группируем по потенциальной площади
    # Для Julietta все legacy — Julietta (единственная площадь пока)
    # Если площадь задана — фильтруем по существованию <base_root>/<area>
    areas = []
    if args.area:
        areas = [args.area]
    else:
        # Сканируем base_root на подкаталоги
        if base_root.exists():
            areas = sorted([d.name for d in base_root.iterdir()
                            if d.is_dir() and not d.name.startswith('.')])

    print(f"Площади для обработки: {areas}")
    print()

    # Мигрируем
    n_ok = 0
    n_skip_exist = 0
    n_skip_nobasedir = 0
    n_err = 0
    actions = []

    for date_str, legacy_path in legacy:
        anchor = parse_legacy_anchor(legacy_path)
        if anchor is None:
            print(f"  [ERR] {legacy_path}: не удалось распарсить")
            n_err += 1
            continue

        # Для каждой площади-кандидата (обычно одна)
        for area in areas:
            base_area = base_root / area
            day_dir = base_area / date_str
            target = day_dir / META_DAY

            if not day_dir.exists():
                # Может быть, базы за этот день нет — пропускаем тихо
                # (это нормально для проектов других площадок в том же conf/)
                n_skip_nobasedir += 1
                continue

            if target.exists() and not args.force:
                print(f"  [SKIP] {target}: уже существует "
                      f"(priority={read_kv(str(target)) and 'area'})")
                n_skip_exist += 1
                continue

            src_rel = os.path.relpath(legacy_path, conf["gnss_experiment"])
            if args.dry_run:
                print(f"  [DRY]  {target}  <-  {src_rel}  "
                      f"lat={anchor['lat']:.9f} lon={anchor['lon']:.9f} "
                      f"h={anchor['h']:.4f}")
                n_ok += 1
                continue

            written, bak = write_day_anchor(
                str(target), anchor, date_str, src_rel, args.no_backup)
            print(f"  [OK]   {written}")
            if bak:
                print(f"         backup: {bak}")
            n_ok += 1
            actions.append((legacy_path, written))

    # Mark migrated
    if args.mark_migrated and actions and not args.dry_run:
        print()
        print("Помечаю legacy как .migrated:")
        for legacy_path, _ in actions:
            new_path = legacy_path + ".migrated"
            if os.path.exists(new_path):
                print(f"  [SKIP] {new_path}: уже существует")
                continue
            shutil.move(legacy_path, new_path)
            print(f"  [OK]   {legacy_path} -> {new_path}")

    # Итог
    print()
    print("=" * 70)
    print(f"  OK:                 {n_ok}")
    print(f"  Skip (уже есть):    {n_skip_exist}")
    print(f"  Skip (нет base_dir):{n_skip_nobasedir}")
    print(f"  Errors:             {n_err}")
    print("=" * 70)
    sys.exit(0 if n_err == 0 else 1)

if __name__ == "__main__":
    main()
