#!/usr/bin/env python3
"""gnss_meta.py — GNSS metadata manager (v1.4.0).

API:
  detect_paths(nov_path)     -> Paths
  read_kv(path)              -> dict | None
  read_anchor(paths)         -> dict | None
  read_base(paths)           -> dict | None
  read_day_anchor(paths)     -> dict | None
  wgs84_to_ecef(lat,lon,h)   -> (x,y,z)
  ecef_to_wgs84(x,y,z)       -> (lat,lon,h)
  check_area(area)           -> [(sev, msg), ...]

CLI:
  resolve <nov>              -> shell-export переменных
  read-anchor <nov>          -> LAT LON H
  read-base <nov>            -> ECEF_X ECEF_Y ECEF_Z
  read-day-anchor <nov>      -> LAT LON H | пусто
  check <nov>                -> отчёт
  check-area <area>          -> отчёт по площади
"""
import os, sys, math, re
from pathlib import Path

META_ANCHOR = ".gnss_anchor.txt"
META_BASE   = ".gnss_base.txt"
META_DAY    = ".gnss_day_anchor.txt"

DEFAULT_EXP = os.path.expanduser("~/gnss_experiment")
CONF_PATH   = os.path.join(DEFAULT_EXP, "conf", "global.conf")

# -------------------- config --------------------

def load_global_conf(path=CONF_PATH):
    """key=value с # comments. Env override."""
    conf = {}
    if os.path.exists(path):
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"): continue
                if "=" not in line: continue
                k, v = line.split("=", 1)
                k = k.strip(); v = v.strip()
                if v.startswith("~"):
                    v = os.path.expanduser(v)
                conf[k] = v
    # env overrides
    if os.environ.get("GNSS_EXPERIMENT"):
        conf["gnss_experiment"] = os.environ["GNSS_EXPERIMENT"]
    if os.environ.get("GNSS_ROVER_ROOT"):
        conf["rover_root"] = os.environ["GNSS_ROVER_ROOT"]
    if os.environ.get("GNSS_BASE_ROOT"):
        conf["base_root"] = os.environ["GNSS_BASE_ROOT"]
    # sanity
    if "gnss_experiment" not in conf:
        conf["gnss_experiment"] = DEFAULT_EXP
    return conf

# -------------------- WGS84 --------------------

WGS84_A  = 6378137.0
WGS84_F  = 1.0 / 298.257223563
WGS84_E2 = 2*WGS84_F - WGS84_F*WGS84_F

def wgs84_to_ecef(lat, lon, h):
    lat_r = math.radians(lat); lon_r = math.radians(lon)
    sin_lat = math.sin(lat_r); cos_lat = math.cos(lat_r)
    N = WGS84_A / math.sqrt(1 - WGS84_E2 * sin_lat * sin_lat)
    x = (N + h) * cos_lat * math.cos(lon_r)
    y = (N + h) * cos_lat * math.sin(lon_r)
    z = (N*(1 - WGS84_E2) + h) * sin_lat
    return x, y, z

def ecef_to_wgs84(x, y, z):
    lon = math.atan2(y, x)
    p = math.sqrt(x*x + y*y)
    lat = math.atan2(z, p * (1 - WGS84_E2))
    for _ in range(8):
        sin_lat = math.sin(lat)
        N = WGS84_A / math.sqrt(1 - WGS84_E2 * sin_lat * sin_lat)
        h = p / math.cos(lat) - N
        lat = math.atan2(z, p * (1 - WGS84_E2 * N / (N + h)))
    sin_lat = math.sin(lat)
    N = WGS84_A / math.sqrt(1 - WGS84_E2 * sin_lat * sin_lat)
    h = p / math.cos(lat) - N
    return math.degrees(lat), math.degrees(lon), h

def llh_ecef_residual(lat, lon, h, ecef_x, ecef_y, ecef_z):
    x, y, z = wgs84_to_ecef(lat, lon, h)
    return math.sqrt((x-ecef_x)**2 + (y-ecef_y)**2 + (z-ecef_z)**2)

# -------------------- path resolution --------------------

def detect_paths(nov_path):
    """<rover_root>/<Area>/<Project>/<file>.NOV -> dict путей."""
    conf = load_global_conf()
    nov = Path(nov_path).expanduser().resolve()
    rover_root = Path(conf["rover_root"]).resolve()
    base_root  = Path(conf["base_root"]).resolve()

    try:
        rel = nov.relative_to(rover_root)
    except ValueError:
        raise ValueError(f"Путь {nov} не под {rover_root}")

    parts = rel.parts
    if len(parts) < 3:
        raise ValueError(f"Ожидалось <Area>/<Project>/<file>, получено: {rel}")
    area    = parts[0]
    project = parts[1]
    date    = project[:8]  # YYYYMMDD из "20260922_1" -> "20260922"

    return {
        "area":       area,
        "project":    project,
        "date":       date,
        "rover_nov":  str(nov),
        "rover_dir":  str(nov.parent),
        "base_dir":   str(base_root / area / date),
        "rover_root": str(rover_root),
        "base_root":  str(base_root),
        "area_rover_dir": str(rover_root / area),
        "area_base_dir":  str(base_root / area),
        "gnss_experiment": conf["gnss_experiment"],
    }

# -------------------- key=value --------------------

def read_kv(path):
    """Парсит key=value с # comments. Возвращает dict или None если файла нет."""
    if not os.path.exists(path): return None
    out = {}
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"): continue
            if "=" not in line: continue
            k, v = line.split("=", 1)
            out[k.strip()] = v.strip()
    return out

def _try_float(d, *keys):
    """Из dict-а извлекает первый доступный ключ и приводит к float."""
    for k in keys:
        if k in d:
            try: return float(d[k])
            except ValueError: pass
    return None

# -------------------- anchors --------------------

def read_area_anchor(paths):
    """1_Data.nosync/<Area>/.gnss_anchor.txt"""
    p = os.path.join(paths["area_rover_dir"], META_ANCHOR)
    if not os.path.exists(p):
        p = os.path.join(paths["area_base_dir"], META_ANCHOR)
    kv = read_kv(p)
    if not kv: return None
    lat = _try_float(kv, "lat", "latitude")
    lon = _try_float(kv, "lon", "longitude")
    h   = _try_float(kv, "h", "height", "alt")
    if lat is None or lon is None or h is None: return None
    return {"lat": lat, "lon": lon, "h": h,
            "source": kv.get("source", ""), "file": p}

def read_day_anchor(paths):
    """2_Diff.nosync/<Area>/<YYYYMMDD>/.gnss_day_anchor.txt"""
    p = os.path.join(paths["base_dir"], META_DAY)
    kv = read_kv(p)
    if not kv: return None
    lat = _try_float(kv, "lat", "latitude")
    lon = _try_float(kv, "lon", "longitude")
    h   = _try_float(kv, "h", "height", "alt")
    if lat is None or lon is None or h is None: return None
    return {"lat": lat, "lon": lon, "h": h,
            "source": kv.get("source", ""), "file": p}

def read_anchor(paths):
    """Приоритет: day → area → legacy conf/ANCHOR_<date>.txt → legacy conf/ANCHOR_<area>.txt.

    Возвращает dict {'lat','lon','h','source','file'} или None.
    """
    da = read_day_anchor(paths)
    if da:
        da["priority"] = "day"
        return da
    aa = read_area_anchor(paths)
    if aa:
        aa["priority"] = "area"
        return aa
    # legacy fallback (conf/)
    exp = paths["gnss_experiment"]
    for fname in (f"ANCHOR_{paths['project']}.txt",
                  f"ANCHOR_{paths['date']}.txt",
                  f"ANCHOR_{paths['area']}.txt"):
        p = os.path.join(exp, "conf", fname)
        if not os.path.exists(p): continue
        with open(p) as f:
            line = f.readline().strip()
        parts = line.split()
        if len(parts) >= 3:
            try:
                lat, lon, h = float(parts[0]), float(parts[1]), float(parts[2])
                return {"lat": lat, "lon": lon, "h": h,
                        "source": "legacy conf/", "file": p,
                        "priority": "legacy"}
            except ValueError:
                pass
    return None

def read_base(paths):
    """2_Diff.nosync/<Area>/.gnss_base.txt, fallback conf/base_ecef.txt.

    Возвращает dict {'lat','lon','h','ecef_x','ecef_y','ecef_z','source','file','priority'}.
    """
    p = os.path.join(paths["area_base_dir"], META_BASE)
    kv = read_kv(p)
    if kv:
        out = {"source": kv.get("source",""), "file": p, "priority": "area"}
        out["lat"] = _try_float(kv, "lat", "latitude")
        out["lon"] = _try_float(kv, "lon", "longitude")
        out["h"]   = _try_float(kv, "h", "height")
        out["ecef_x"] = _try_float(kv, "ecef_x", "x")
        out["ecef_y"] = _try_float(kv, "ecef_y", "y")
        out["ecef_z"] = _try_float(kv, "ecef_z", "z")
        if out["ecef_x"] is None or out["ecef_y"] is None or out["ecef_z"] is None:
            if out["lat"] is not None and out["lon"] is not None and out["h"] is not None:
                x, y, z = wgs84_to_ecef(out["lat"], out["lon"], out["h"])
                out["ecef_x"], out["ecef_y"], out["ecef_z"] = x, y, z
        return out
    # legacy
    p2 = os.path.join(paths["gnss_experiment"], "conf", "base_ecef.txt")
    if os.path.exists(p2):
        with open(p2) as f:
            line = f.readline().strip()
        parts = line.split()
        if len(parts) >= 3:
            try:
                x, y, z = float(parts[0]), float(parts[1]), float(parts[2])
                lat, lon, h = ecef_to_wgs84(x, y, z)
                return {"ecef_x": x, "ecef_y": y, "ecef_z": z,
                        "lat": lat, "lon": lon, "h": h,
                        "source": "legacy conf/base_ecef.txt",
                        "file": p2, "priority": "legacy"}
            except ValueError:
                pass
    return None

# -------------------- check --------------------

def check_area(area, base_root=None, rover_root=None):
    """Валидация метаданных площади. Возвращает [(sev, msg), ...]."""
    conf = load_global_conf()
    if base_root is None:
        base_root = conf["base_root"]
    if rover_root is None:
        rover_root = conf["rover_root"]
    reports = []

    rover_area = Path(rover_root) / area
    base_area  = Path(base_root) / area

    # anchor
    pa = rover_area / META_ANCHOR
    if not pa.exists():
        pa = base_area / META_ANCHOR
    if not pa.exists():
        reports.append(("WARN", f"нет anchor площади: {pa}"))
    else:
        kv = read_kv(str(pa))
        if not kv:
            reports.append(("ERR", f"пустой или битый {pa}"))
        else:
            lat = _try_float(kv, "lat"); lon = _try_float(kv, "lon"); h = _try_float(kv, "h")
            if lat is None or lon is None or h is None:
                reports.append(("ERR", f"{pa}: нет lat/lon/h"))
            else:
                if not (-90 <= lat <= 90):
                    reports.append(("ERR", f"{pa}: lat={lat} вне [-90,90]"))
                if not (-180 <= lon <= 180):
                    reports.append(("ERR", f"{pa}: lon={lon} вне [-180,180]"))
                if not (-500 <= h <= 9000):
                    reports.append(("WARN", f"{pa}: h={h} вне [-500,9000]"))
                reports.append(("OK", f"anchor: lat={lat:.9f} lon={lon:.9f} h={h:.4f}"))

    # base
    pb = base_area / META_BASE
    if not pb.exists():
        reports.append(("WARN", f"нет base: {pb}"))
    else:
        kv = read_kv(str(pb))
        if not kv:
            reports.append(("ERR", f"пустой или битый {pb}"))
        else:
            lat = _try_float(kv, "lat"); lon = _try_float(kv, "lon"); h = _try_float(kv, "h")
            x = _try_float(kv, "ecef_x"); y = _try_float(kv, "ecef_y"); z = _try_float(kv, "ecef_z")
            if lat is None or lon is None or h is None:
                reports.append(("ERR", f"{pb}: нет lat/lon/h"))
            elif x is None or y is None or z is None:
                reports.append(("WARN", f"{pb}: нет ecef, будет рассчитан из LLH"))
            else:
                res = llh_ecef_residual(lat, lon, h, x, y, z)
                if res > 0.05:
                    reports.append(("ERR", f"{pb}: LLH↔ECEF residual = {res:.4f} м (>5 см)"))
                else:
                    reports.append(("OK", f"base: LLH↔ECEF residual = {res:.4f} м"))

    # day anchors
    if base_area.exists():
        days = sorted([d for d in base_area.iterdir() if d.is_dir() and re.match(r'^\d{8}', d.name)])
        n_with = 0
        for d in days:
            p = d / META_DAY
            if p.exists():
                kv = read_kv(str(p))
                if kv:
                    dlat = _try_float(kv, "lat"); dlon = _try_float(kv, "lon")
                    if dlat is not None and dlon is not None and pa.exists():
                        akv = read_kv(str(pa)) or {}
                        alat = _try_float(akv, "lat"); alon = _try_float(akv, "lon")
                        if alat is not None and alon is not None:
                            d_m = math.sqrt(((dlat-alat)*111000)**2 +
                                            ((dlon-alon)*111000*math.cos(math.radians(alat)))**2)
                            if d_m > 100:
                                reports.append(("WARN", f"{d.name}: day anchor в {d_m:.0f} м от area anchor"))
                            else:
                                reports.append(("OK", f"{d.name}: day anchor в {d_m:.1f} м от area"))
                    n_with += 1
        reports.append(("OK", f"дней с day anchor: {n_with} из {len(days)}"))
    return reports

# -------------------- CLI --------------------

def _print_report(reports, verbose=True):
    ok = sum(1 for s,_ in reports if s == "OK")
    warn = sum(1 for s,_ in reports if s == "WARN")
    err = sum(1 for s,_ in reports if s == "ERR")
    for sev, msg in reports:
        if not verbose and sev == "OK": continue
        print(f"[{sev}] {msg}")
    print(f"# итого: OK={ok} WARN={warn} ERR={err}")
    return 0 if err == 0 else 1

def _cmd_resolve(args):
    paths = detect_paths(args[0])
    # shell-eval формат
    for k, v in paths.items():
        if k == "gnss_experiment":
            env = "GNSS_EXPERIMENT"
        else:
            env = "GNSS_" + k.upper()
        print(f'export {env}="{v}"')
    return 0

def _cmd_read_anchor(args):
    paths = detect_paths(args[0])
    a = read_anchor(paths)
    if not a: return 2
    print(f'{a["lat"]:.9f} {a["lon"]:.9f} {a["h"]:.4f}')
    print(f'# source: {a["source"]} priority: {a["priority"]} file: {a["file"]}',
          file=sys.stderr)
    return 0

def _cmd_read_base(args):
    paths = detect_paths(args[0])
    b = read_base(paths)
    if not b: return 2
    print(f'{b["ecef_x"]:.4f} {b["ecef_y"]:.4f} {b["ecef_z"]:.4f}')
    print(f'# source: {b["source"]} priority: {b["priority"]} file: {b["file"]}',
          file=sys.stderr)
    return 0

def _cmd_read_day_anchor(args):
    paths = detect_paths(args[0])
    d = read_day_anchor(paths)
    if not d: return 2
    print(f'{d["lat"]:.9f} {d["lon"]:.9f} {d["h"]:.4f}')
    return 0

def _cmd_check(args):
    paths = detect_paths(args[0])
    reports = []
    a = read_anchor(paths)
    if a:
        reports.append(("OK", f'anchor ({a["priority"]}): '
                       f'lat={a["lat"]:.9f} lon={a["lon"]:.9f} h={a["h"]:.4f}'))
    else:
        reports.append(("ERR", "anchor не найден"))
    b = read_base(paths)
    if b:
        res = llh_ecef_residual(b["lat"], b["lon"], b["h"], b["ecef_x"], b["ecef_y"], b["ecef_z"])
        reports.append(("OK", f'base ({b["priority"]}): ECEF '
                       f'{b["ecef_x"]:.4f} {b["ecef_y"]:.4f} {b["ecef_z"]:.4f} '
                       f'(LLH↔ECEF res = {res:.4f} м)'))
    else:
        reports.append(("ERR", "base не найден"))
    return _print_report(reports, verbose=True)

def _cmd_check_area(args):
    reports = check_area(args[0])
    return _print_report(reports, verbose=True)

def main():
    if len(sys.argv) < 2:
        print(__doc__); sys.exit(1)
    cmd = sys.argv[1]
    rest = sys.argv[2:]
    table = {
        "resolve":         _cmd_resolve,
        "read-anchor":     _cmd_read_anchor,
        "read-base":       _cmd_read_base,
        "read-day-anchor": _cmd_read_day_anchor,
        "check":           _cmd_check,
        "check-area":      _cmd_check_area,
    }
    if cmd not in table:
        print(f"unknown cmd: {cmd}", file=sys.stderr)
        print(__doc__); sys.exit(1)
    if not rest:
        print(f"usage: gnss_meta.py {cmd} <arg>", file=sys.stderr); sys.exit(1)
    sys.exit(table[cmd](rest))

if __name__ == "__main__":
    main()
