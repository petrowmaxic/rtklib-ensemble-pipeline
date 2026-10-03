#!/usr/bin/env python3
"""gnss_area_init.py — мастер инициализации новой площади (v1.4.1).

Создаёт в base_root/<Area>/:
    .gnss_anchor.txt   — anchor площади (WGS84 LLH)
    .gnss_base.txt     — координаты базы (LLH + ECEF)
    STRUCTURE.md       — описание структуры директории

Usage:
    gnss_area_init.py                                    # интерактивно
    gnss_area_init.py --area Julietta \
        --base-llh 61.161226811 154.014501730 831.9280 \
        --anchor-llh 61.161609573 154.015098774 832.4611 \
        --non-interactive
"""
import os, sys, re, shutil, argparse
from pathlib import Path
from datetime import datetime

EXP = os.path.expanduser("~/gnss_experiment")
sys.path.insert(0, os.path.join(EXP, "scripts"))
from gnss_meta import (load_global_conf, wgs84_to_ecef, ecef_to_wgs84,
                       llh_ecef_residual, read_kv, META_ANCHOR, META_BASE)

AREA_RE = re.compile(r'^[A-Za-z][A-Za-z0-9_]*$')

# -------------------- validation --------------------

def validate_area_name(s):
    if not AREA_RE.match(s):
        return "Только латиница/цифры/подчёркивание, начинается с буквы"
    return None

def validate_lat(v):
    return None if -90 <= v <= 90 else f"lat={v} вне [-90, 90]"

def validate_lon(v):
    return None if -180 <= v <= 180 else f"lon={v} вне [-180, 180]"

def validate_h(v):
    return None if -500 <= v <= 9000 else f"h={v} вне [-500, 9000]"

# -------------------- prompts --------------------

def ask(prompt, default=None, validate=None):
    """Интерактивный prompt с дефолтом и валидатором."""
    while True:
        suffix = f" [{default}]" if default is not None else ""
        try:
            s = input(f"  {prompt}{suffix}: ").strip()
        except EOFError:
            print("\n  ERROR: EOF при интерактивном вводе", file=sys.stderr)
            sys.exit(2)
        if not s and default is not None:
            s = str(default)
        if not s:
            print("  ⚠ пустой ввод", file=sys.stderr)
            continue
        if validate:
            err = validate(s)
            if err:
                print(f"  ⚠ {err}", file=sys.stderr)
                continue
        return s

def ask_float(prompt, default=None, validate=None):
    while True:
        s = ask(prompt, default=default)
        try:
            v = float(s)
        except ValueError:
            print(f"  ⚠ не число: {s}", file=sys.stderr)
            continue
        if validate:
            err = validate(v)
            if err:
                print(f"  ⚠ {err}", file=sys.stderr)
                continue
        return v

def ask_choice(prompt, choices, default=None):
    """choices — список строк (без указания в prompt, показываем как [a/b/c])."""
    show = "/".join(choices)
    if default:
        show += f" (default={default})"
    while True:
        try:
            s = input(f"  {prompt} [{show}]: ").strip().lower()
        except EOFError:
            sys.exit(2)
        if not s and default:
            return default
        if s in [c.lower() for c in choices]:
            return s
        print(f"  ⚠ выберите: {show}", file=sys.stderr)

def ask_yes_no(prompt, default='N'):
    return ask_choice(prompt, ['y', 'n'], default=default) == 'y'

# -------------------- collection --------------------

def collect_base_coords(interactive, base_llh=None, base_ecef=None):
    """Возвращает dict с lat/lon/h/ecef_x/ecef_y/ecef_z."""
    if base_llh:
        lat, lon, h = base_llh
        x, y, z = wgs84_to_ecef(lat, lon, h)
        print(f"  base LLH: lat={lat:.9f} lon={lon:.9f} h={h:.4f}")
        print(f"  → ECEF: {x:.4f} {y:.4f} {z:.4f}")
        return {'lat': lat, 'lon': lon, 'h': h,
                'ecef_x': x, 'ecef_y': y, 'ecef_z': z}
    if base_ecef:
        x, y, z = base_ecef
        lat, lon, h = ecef_to_wgs84(x, y, z)
        print(f"  base ECEF: {x:.4f} {y:.4f} {z:.4f}")
        print(f"  → LLH: lat={lat:.9f} lon={lon:.9f} h={h:.4f}")
        return {'lat': lat, 'lon': lon, 'h': h,
                'ecef_x': x, 'ecef_y': y, 'ecef_z': z}
    if not interactive:
        raise ValueError("base coords не заданы (нужен --base-llh или --base-ecef)")

    print()
    fmt = ask_choice("Формат координат базы", ['llh', 'ecef'], default='llh')
    if fmt == 'llh':
        lat = ask_float("lat (deg)", validate=validate_lat)
        lon = ask_float("lon (deg)", validate=validate_lon)
        h   = ask_float("h (m)",   validate=validate_h)
        x, y, z = wgs84_to_ecef(lat, lon, h)
        print(f"  → ECEF: {x:.4f} {y:.4f} {z:.4f}")
        return {'lat': lat, 'lon': lon, 'h': h,
                'ecef_x': x, 'ecef_y': y, 'ecef_z': z}
    else:
        x = ask_float("X (m)")
        y = ask_float("Y (m)")
        z = ask_float("Z (m)")
        lat, lon, h = ecef_to_wgs84(x, y, z)
        print(f"  → LLH: lat={lat:.9f} lon={lon:.9f} h={h:.4f}")
        return {'lat': lat, 'lon': lon, 'h': h,
                'ecef_x': x, 'ecef_y': y, 'ecef_z': z}

def collect_anchor_coords(interactive, anchor_llh=None, anchor_skip=False):
    """Возвращает dict {'lat','lon','h'} или None если skip."""
    if anchor_skip:
        return None
    if anchor_llh:
        lat, lon, h = anchor_llh
        print(f"  anchor LLH: lat={lat:.9f} lon={lon:.9f} h={h:.4f}")
        return {'lat': lat, 'lon': lon, 'h': h}
    if not interactive:
        return None
    print()
    if not ask_yes_no("Задать anchor площади?", default='Y'):
        return None
    lat = ask_float("lat (deg)", validate=validate_lat)
    lon = ask_float("lon (deg)", validate=validate_lon)
    h   = ask_float("h (m)",   validate=validate_h)
    return {'lat': lat, 'lon': lon, 'h': h}

# -------------------- writers --------------------

def backup_if_exists(path):
    """Если файл существует — копирует в .bak_<ts> и возвращает путь бэкапа."""
    p = Path(path)
    if not p.exists():
        return None
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    bak = p.parent / (p.name + f".bak_{ts}")
    shutil.copy2(p, bak)
    return str(bak)

def _write_kv(path, header, data, source):
    """key=value writer с заголовком-комментарием."""
    lines = []
    lines.append(f"# {header}")
    lines.append(f"# Создано: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"# Source: {source}")
    lines.append(f"# Формат: key=value, # comments (см. gnss_meta.py)")
    lines.append("")
    for k, v in data.items():
        if isinstance(v, float):
            lines.append(f"{k} = {v:.9f}" if k in ('lat','lon') else f"{k} = {v:.4f}")
        else:
            lines.append(f"{k} = {v}")
    lines.append("")
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        f.write("\n".join(lines))

def write_anchor(path, anchor, area, source):
    data = {'lat': anchor['lat'], 'lon': anchor['lon'], 'h': anchor['h'],
            'source': source}
    _write_kv(path, f"GNSS Anchor — {area}", data, source)

def write_base(path, base, area, source):
    data = {
        'lat': base['lat'], 'lon': base['lon'], 'h': base['h'],
        'ecef_x': base['ecef_x'], 'ecef_y': base['ecef_y'], 'ecef_z': base['ecef_z'],
        'source': source,
    }
    _write_kv(path, f"GNSS Base — {area}", data, source)

# -------------------- STRUCTURE.md --------------------

STRUCTURE_TEMPLATE = """# {area} — Base Station Data Directory

Область: **{area}**
Создано: {created}
Источник: gnss_area_init.py v1.4.1

## Структура
{area}/
├── .gnss_anchor.txt ← Anchor площади (WGS84 LLH, постоянный)
├── .gnss_base.txt ← Координаты базы (WGS84 LLH + ECEF)
├── STRUCTURE.md ← этот файл
└── <YYYYMMDD>/ ← Данные базы за день
├── .gnss_day_anchor.txt ← Дневной якорь (если отличается от площади)
├── gnss_*.ubx ← Сырые данные базы
└── merged.ubx ← Слитые (если было несколько сегментов)

## Метаданные

### `.gnss_anchor.txt` — anchor площади

Постоянная точка площадки (точка взлёта/посадки вертолёта).
Не меняется в течение всей работы на площади, кроме случаев
методических работ (ежедневная калибровка гамма-спектрального
комплекса по отношению к Торию).

Формат: key=value, см. `gnss_meta.py`.

### `.gnss_base.txt` — координаты базы

Координаты базовой станции в двух форматах:
- WGS84 LLH (lat/lon/h) — для геофизика
- ECEF (ecef_x/ecef_y/ecef_z) — для RTKLIB

### `.gnss_day_anchor.txt` — дневной якорь

Опционально. Используется, если якорь конкретного дня отличается
от якоря площади. Приоритет в `gnss_meta.read_anchor`:
**day → area → legacy conf/**.

## Обработка
~/gnss_experiment/scripts/pipeline.sh <rover.NOV> <base.ubx|base_dir>

Метаданные подхватываются автоматически через `gnss_meta.py`.
"""

def write_structure_md(path, area, anchor_path, base_path, source):
    text = STRUCTURE_TEMPLATE.format(
        area=area,
        created=datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    text += f"\n## Anchor / Base пути\n\n"
    text += f"- Anchor: `{anchor_path}`\n"
    text += f"- Base:   `{base_path}`\n"
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        f.write(text)

# -------------------- main --------------------

def main():
    parser = argparse.ArgumentParser(
        description="Мастер инициализации новой GNSS площади (v1.4.1)")
    parser.add_argument('--area', type=str)
    parser.add_argument('--base-root', type=str,
                        help='Override base_root (иначе из global.conf)')
    parser.add_argument('--rover-root', type=str,
                        help='Override rover_root (иначе из global.conf)')
    parser.add_argument('--base-llh', nargs=3, type=float,
                        metavar=('LAT','LON','H'))
    parser.add_argument('--base-ecef', nargs=3, type=float,
                        metavar=('X','Y','Z'))
    parser.add_argument('--anchor-llh', nargs=3, type=float,
                        metavar=('LAT','LON','H'))
    parser.add_argument('--anchor-skip', action='store_true',
                        help='Не создавать anchor площади')
    parser.add_argument('--non-interactive', action='store_true')
    parser.add_argument('--force', action='store_true',
                        help='Перезаписать существующие файлы без вопроса')
    parser.add_argument('--source', type=str, default='wizard',
                        help='Метка источника (по умолчанию: wizard)')
    args = parser.parse_args()

    conf = load_global_conf()
    if args.rover_root:
        conf['rover_root'] = os.path.expanduser(args.rover_root)
    if args.base_root:
        conf['base_root'] = os.path.expanduser(args.base_root)
    interactive = not args.non_interactive

    print("=" * 60)
    print("  GNSS Area Initialization Wizard (v1.4.1)")
    print("=" * 60)

    # 1) Area name
    print(f"\n[1/5] Название площади")
    if args.area:
        err = validate_area_name(args.area)
        if err:
            print(f"ERROR: --area '{args.area}': {err}", file=sys.stderr)
            sys.exit(1)
        area = args.area
        print(f"  {area}")
    elif interactive:
        area = ask("Area name", validate=validate_area_name)
    else:
        print("ERROR: --area обязателен в --non-interactive", file=sys.stderr)
        sys.exit(1)

    # 2) roots
    print(f"\n[2/5] Корневые директории")
    rover_root = conf.get('rover_root', os.path.expanduser('~/Documents/1_Data.nosync'))
    base_root  = conf.get('base_root',  os.path.expanduser('~/Documents/2_Diff.nosync'))
    if interactive:
        rover_root = ask("rover_root", default=rover_root)
        base_root  = ask("base_root",  default=base_root)
    else:
        print(f"  rover_root: {rover_root}")
        print(f"  base_root:  {base_root}")

    area_base_dir  = Path(base_root) / area
    anchor_path    = area_base_dir / META_ANCHOR
    base_path      = area_base_dir / META_BASE
    structure_path = area_base_dir / "STRUCTURE.md"

    # 3) Base coords
    print(f"\n[3/5] Координаты базы")
    try:
        base = collect_base_coords(interactive, args.base_llh, args.base_ecef)
    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    # 4) Anchor coords
    print(f"\n[4/5] Anchor площади")
    anchor = collect_anchor_coords(interactive, args.anchor_llh, args.anchor_skip)

    # 5) Summary + confirm
    print(f"\n[5/5] Сводка")
    print(f"  area:        {area}")
    print(f"  rover_root:  {rover_root}")
    print(f"  base_root:   {base_root}")
    print(f"  anchor file: {anchor_path}")
    print(f"  base file:   {base_path}")
    print(f"  STRUCTURE:   {structure_path}")
    print()
    if anchor:
        print(f"  anchor: lat={anchor['lat']:.9f} lon={anchor['lon']:.9f} h={anchor['h']:.4f}")
    else:
        print(f"  anchor: (не задан)")
    print(f"  base:   lat={base['lat']:.9f} lon={base['lon']:.9f} h={base['h']:.4f}")
    print(f"          ECEF {base['ecef_x']:.4f} {base['ecef_y']:.4f} {base['ecef_z']:.4f}")
    res = llh_ecef_residual(base['lat'], base['lon'], base['h'],
                            base['ecef_x'], base['ecef_y'], base['ecef_z'])
    print(f"  LLH↔ECEF residual = {res:.4f} м")
    print()

    # Проверка существования
    existing = [p for p in [anchor_path, base_path, structure_path] if p.exists()]
    if existing:
        print(f"  ⚠ существуют: {len(existing)} файл(ов)")
        for p in existing:
            print(f"    - {p}")
        if interactive and not args.force:
            if not ask_yes_no("Перезаписать (с бэкапом)?", default='N'):
                print("Отменено.")
                sys.exit(0)
        elif not interactive and not args.force:
            print(f"ERROR: файлы существуют, --force для перезаписи", file=sys.stderr)
            sys.exit(1)

    if interactive and not args.force:
        if not ask_yes_no("Записать?", default='Y'):
            print("Отменено.")
            sys.exit(0)

    # Запись
    print()
    baks = []
    for p in [anchor_path, base_path, structure_path]:
        bak = backup_if_exists(str(p))
        if bak:
            baks.append(bak)

    if anchor:
        write_anchor(str(anchor_path), anchor, area, args.source)
        print(f"  ✓ {anchor_path}")
    else:
        print(f"  (anchor не создан — не задан)")

    write_base(str(base_path), base, area, args.source)
    print(f"  ✓ {base_path}")

    write_structure_md(str(structure_path), area,
                       str(anchor_path) if anchor else "(не задан)",
                       str(base_path), args.source)
    print(f"  ✓ {structure_path}")

    for b in baks:
        print(f"  backup: {b}")

    # Финальная валидация
    print()
    print("=" * 60)
    print(f"  Проверка: gnss_meta.py check-area {area}")
    print("=" * 60)
    from gnss_meta import check_area
    reports = check_area(area, base_root=str(base_root), rover_root=str(rover_root))
    for sev, msg in reports:
        print(f"  [{sev}] {msg}")

    errs = sum(1 for s, _ in reports if s == "ERR")
    sys.exit(0 if errs == 0 else 1)

if __name__ == "__main__":
    main()
