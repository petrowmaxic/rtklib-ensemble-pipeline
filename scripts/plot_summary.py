#!/usr/bin/env python3
"""plot_summary.py -- интерактивный HTML-отчёт для одного проекта (v1.5.0).

4 вкладки (создаются, только если есть источники):
  A: raw (e15_forward) vs processed (result.pos)
  B: orig Viterbi vs segmented (опционально)
  C: best run vs ensemble (опционально)
  D: наш vs GrafNav .xyz (опционально)

Usage:
  plot_summary.py <result.pos> [--seg-dir DIR] [--grafnav FILE] [--out FILE]
                  [--standalone] [--title STR]
"""
import os, sys, math, argparse, json
from datetime import datetime, timedelta
from pathlib import Path

# --- LTTB (Largest-Triangle-Three-Buckets) для downsampling ---
def lttb(xs, ys, n_out):
    """Downsample до n_out точек, сохраняя пики.
    Внутренне сортирует по X (нужно для backward-порядка .pos)."""
    pairs = sorted(zip(xs, ys))
    xs = [p[0] for p in pairs]
    ys = [p[1] for p in pairs]
    n = len(xs)
    if n <= n_out or n_out < 3:
        return xs, ys
    sampled_x = [xs[0]]
    sampled_y = [ys[0]]
    every = (n - 2) / (n_out - 2)
    a = 0
    for i in range(n_out - 2):
        avg_range_start = int(math.floor((i + 1) * every)) + 1
        avg_range_end = int(math.floor((i + 2) * every)) + 1
        avg_range_end = min(avg_range_end, n)
        avg_x = 0.0; avg_y = 0.0; avg_n = avg_range_end - avg_range_start
        if avg_n < 1: avg_n = 1
        for j in range(avg_range_start, avg_range_end):
            avg_x += xs[j]; avg_y += ys[j]
        avg_x /= avg_n; avg_y /= avg_n
        range_offs = int(math.floor(i * every)) + 1
        range_to = int(math.floor((i + 1) * every)) + 1
        point_a_x = xs[a]; point_a_y = ys[a]
        max_area = -1.0; next_a = range_offs
        for j in range(range_offs, range_to):
            area = abs((point_a_x - avg_x) * (ys[j] - point_a_y)
                       - (point_a_x - xs[j]) * (avg_y - point_a_y)) * 0.5
            if area > max_area:
                max_area = area; next_a = j
        sampled_x.append(xs[next_a])
        sampled_y.append(ys[next_a])
        a = next_a
    sampled_x.append(xs[-1])
    sampled_y.append(ys[-1])
    return sampled_x, sampled_y

# --- Загрузка .pos ---
def r100(t):
    return t.replace(microsecond=(t.microsecond // 100000) * 100000)

def load_pos(path):
    """Возвращает dict: t -> {'lat','lon','h','q','ns','ratio','age','sdu'}"""
    out = {}
    if not os.path.exists(path): return out
    with open(path) as f:
        for line in f:
            if line.startswith('%') or not line.strip(): continue
            x = line.split()
            if len(x) < 6: continue
            try:
                dt = datetime.strptime(f"{x[0]} {x[1]}", "%Y/%m/%d %H:%M:%S.%f")
                lat = float(x[2]); lon = float(x[3]); h = float(x[4])
                q = int(x[5]); ns = int(x[6]) if len(x) > 6 else 0
                sdu = float(x[9]) if len(x) > 9 else 0.0
                age = float(x[13]) if len(x) > 13 else 0.0
                ratio = float(x[14]) if len(x) > 14 else 0.0
            except (ValueError, IndexError):
                continue
            out[r100(dt)] = {'lat': lat, 'lon': lon, 'h': h, 'q': q,
                             'ns': ns, 'sdu': sdu, 'age': age, 'ratio': ratio}
    return out

# --- Загрузка GrafNav .xyz ---
def load_grafnav(path):
    """Возвращает dict: t -> (lat, lon, h)"""
    out = {}
    if not os.path.exists(path): return out
    with open(path) as f:
        for line in f:
            if line.startswith('/') or not line.strip(): continue
            x = line.split()
            if len(x) < 5: continue
            try:
                date_s = x[0]; time_s = x[1]
                y, mo, d_ = date_s.split('/')
                hh, mm, ss = time_s.split(':')
                sec = float(ss)
                dt = datetime(int(y), int(mo), int(d_), int(hh), int(mm),
                              int(sec), int(round((sec - int(sec)) * 1e6)))
            except (ValueError, IndexError):
                continue
            out[r100(dt)] = (float(x[3]), float(x[2]), float(x[4]))
    return out

# --- Загрузка .stat (DOP) ---
def load_stat(path):
    """Парсит $POS-записи: возвращает dict (week,tow) -> (x,y,z,sdx,sdy,sdz)"""
    out = {}
    if not os.path.exists(path): return {}
    with open(path) as f:
        for line in f:
            if not line.startswith('$POS,'): continue
            parts = line.rstrip().split(',')
            if len(parts) < 10: continue
            try:
                week = int(parts[1]); tow = float(parts[2])
                x = float(parts[3]); y = float(parts[4]); z = float(parts[5])
                sdx = float(parts[6]); sdy = float(parts[7]); sdz = float(parts[8])
            except (ValueError, IndexError):
                continue
            out[(week, round(tow, 3))] = (x, y, z, sdx, sdy, sdz)
    return out


# ==================== Построители панелей ====================

def _sec(t0, t):
    """Секунды от t0."""
    return (t - t0).total_seconds()

GPS_EPOCH = datetime(1980, 1, 6)

def week_tow_to_dt(week, tow):
    """GPST week+tow -> datetime."""
    return GPS_EPOCH + timedelta(weeks=week, seconds=tow)


def compute_segments(times_sorted, gap_thr=300.0):
    """Возвращает список (start_dt, end_dt) сегментов, где gap > gap_thr."""
    if not times_sorted: return []
    segs = []; start = times_sorted[0]
    for i in range(1, len(times_sorted)):
        if (times_sorted[i] - times_sorted[i-1]).total_seconds() > gap_thr:
            segs.append((start, times_sorted[i-1]))
            start = times_sorted[i]
    segs.append((start, times_sorted[-1]))
    return [s for s in segs if (s[1] - s[0]).total_seconds() >= 60]


def make_q_heatmap(t0, times, qs, title):
    """Heatmap: время (сек) × полосы Q1/Q2/Q4/Q5."""
    if not times:
        return None
    x_sec = [_sec(t0, t) for t in times]
    z = []
    y_labels = ['Q1', 'Q2', 'Q3', 'Q4', 'Q5', 'Q6']
    q_map = {1: 0, 2: 1, 3: 2, 4: 3, 5: 4, 6: 5}
    for y_idx in range(6):
        row = []
        for q in qs:
            row.append(1.0 if q_map.get(q, -1) == y_idx else 0.0)
        z.append(row)
    return {
        'type': 'heatmap',
        'x': x_sec,
        'y': y_labels,
        'z': z,
        'colorscale': [[0, '#f0f0f0'], [1, '#1f77b4']],
        'showscale': False,
        'hovertemplate': '%{x:.1f} с<br>%{y}<extra></extra>',
        'name': title,
    }


def make_line(t0, times, ys, title, ylabel, color='#1f77b4',
              n_out=1000, seg_bounds=None):
    """Line plot с LTTB и опциональными границами сегментов."""
    if not times:
        return None
    x_raw = [_sec(t0, t) for t in times]
    xs, yds = lttb(x_raw, ys, n_out)
    trace = {
        'type': 'scattergl',
        'mode': 'lines',
        'x': xs,
        'y': yds,
        'name': title,
        'line': {'color': color, 'width': 1},
        'hovertemplate': 't=%{x:.1f} с<br>' + ylabel + '=%{y:.2f}<extra></extra>',
    }
    return trace


def make_segment_shapes(t0, seg_bounds, y_ref=None):
    """Формирует shapes (вертикальные линии) на границах сегментов."""
    shapes = []
    for i, (s, e) in enumerate(seg_bounds):
        x_start = _sec(t0, s)
        shapes.append({
            'type': 'line', 'x0': x_start, 'x1': x_start,
            'y0': 0, 'y1': 1, 'yref': 'paper',
            'line': {'color': 'rgba(200,50,50,0.4)', 'width': 1, 'dash': 'dot'},
        })
    return shapes


def stats_line(values):
    """Быстрая статистика для аннотации."""
    if not values: return {}
    s = sorted(values); n = len(s)
    return {
        'n': n,
        'median': s[n//2],
        'p90': s[int(0.9 * n)],
        'max': s[-1],
        'mean': sum(s) / n,
    }


def dist_3d(a, b):
    """Расстояние между двумя dicts с lat/lon/h или tuple."""
    if isinstance(a, dict):
        lat1, lon1, h1 = a['lat'], a['lon'], a['h']
    else:
        lat1, lon1, h1 = a[0], a[1], a[2]
    if isinstance(b, dict):
        lat2, lon2, h2 = b['lat'], b['lon'], b['h']
    else:
        lat2, lon2, h2 = b[0], b[1], b[2]
    R = 6371000.0
    lat_mid = math.radians((lat1 + lat2) / 2.0)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    dn = dlat * R
    de = dlon * R * math.cos(lat_mid)
    dh = h2 - h1
    return math.sqrt(dn*dn + de*de + dh*dh), abs(dh)

import glob

# ==================== Загрузка ансамбля ====================

def load_runs_from_segs(seg_dirs):
    """Загружает все прогоны из seg_*/ / ensemble/.
    Возвращает dict: run_name -> {t: {'h','q','ratio'}}.
    """
    runs = {}
    if not seg_dirs:
        return runs
    for d in seg_dirs:
        if not os.path.isdir(d): continue
        for f in sorted(glob.glob(os.path.join(d, '*.pos'))):
            base = os.path.basename(f)
            if '_events' in base: continue
            name = base[:-4]
            if name not in runs:
                runs[name] = {}
            with open(f) as fp:
                for line in fp:
                    if line.startswith('%') or not line.strip(): continue
                    x = line.split()
                    if len(x) < 6: continue
                    try:
                        dt = datetime.strptime(f"{x[0]} {x[1]}",
                                               "%Y/%m/%d %H:%M:%S.%f")
                        lat = float(x[2]); lon = float(x[3]); h = float(x[4])
                        q = int(x[5])
                        ratio = float(x[14]) if len(x) > 14 else 0.0
                    except (ValueError, IndexError):
                        continue
                    runs[name][r100(dt)] = {'lat': lat, 'lon': lon, 'h': h,
                                            'q': q, 'ratio': ratio}
    return runs


def best_single_run(runs):
    """Прогон с максимальным Q1% (без viterbi/result/ensemble)."""
    EXCLUDE = ('viterbi', 'result', 'ensemble')
    best = None; best_pct = -1.0
    for name, d in runs.items():
        if not d: continue
        if any(e in name.lower() for e in EXCLUDE): continue
        q1 = sum(1 for r in d.values() if r['q'] == 1)
        pct = q1 / len(d)
        if pct > best_pct:
            best_pct = pct; best = name
    return best, best_pct


def spread_and_count(runs, times):
    """Для каждой эпохи: spread (max-min h) и число прогонов с Q=1."""
    spread = {}; n_fix = {}
    for t in times:
        hs = []; nf = 0
        for name, d in runs.items():
            r = d.get(t)
            if r and r['q'] == 1:
                hs.append(r['h']); nf += 1
        if len(hs) >= 2:
            spread[t] = max(hs) - min(hs)
        n_fix[t] = nf
    return spread, n_fix


def make_panel(title, traces, yaxis_title, shapes=None):
    """Обёртка панели для передачи в JSON."""
    return {
        'title': title,
        'traces': [t for t in traces if t is not None],
        'shapes': shapes or [],
        'yaxis_title': yaxis_title,
    }


# ==================== Вкладка A ====================

def build_tab_a(result_pos_path, seg_dirs):
    """A: raw (e15_forward) vs processed (result.pos)."""
    res = load_pos(result_pos_path)
    if not res: return None
    runs = load_runs_from_segs(seg_dirs)
    raw = runs.get('e15_forward', {})
    if not raw: return None
    common = sorted(set(res) & set(raw))
    if not common: return None
    t0 = common[0]
    segs = compute_segments(common)
    shapes = make_segment_shapes(t0, segs)

    # Panel 1: Q-value
    q_trace = make_q_heatmap(t0, common, [res[t]['q'] for t in common], 'Q')

    # Панели dLat / dLon / dH = processed (result) − raw (e15_forward)
    dlat = []; dlon = []; dh = []
    for t in common:
        a = raw[t]; b = res[t]
        R = 6371000.0
        lat_mid = math.radians((a['lat'] + b['lat']) / 2.0)
        dlat.append((b['lat'] - a['lat']) * R)
        dlon.append((b['lon'] - a['lon']) * R * math.cos(lat_mid))
        dh.append(b['h'] - a['h'])

    tr_dlat = make_line(t0, common, dlat, 'dLat', 'м', color='#d62728', n_out=2000)
    tr_dlon = make_line(t0, common, dlon, 'dLon', 'м', color='#9467bd', n_out=2000)
    tr_dh   = make_line(t0, common, dh,   'dH',   'м', color='#8c564b', n_out=2000)

    panels = [
        make_panel('Q-value', [q_trace], 'категория', shapes),
        make_panel('dLat = processed − raw, м', [tr_dlat], 'м', shapes),
        make_panel('dLon = processed − raw, м', [tr_dlon], 'м', shapes),
        make_panel('dH = processed − raw, м', [tr_dh], 'м', shapes),
    ]
    return {
        'name': 'A: Raw vs Processed',
        'panels': panels,
        'annotation': {
            'n_common': len(common),
            'dh_stats': stats_line(dh),
        },
    }


# ==================== Вкладка C ====================

def build_tab_c(result_pos_path, seg_dirs):
    """C: ensemble vs best single + spread между 8."""
    res = load_pos(result_pos_path)
    if not res: return None
    runs = load_runs_from_segs(seg_dirs)
    if len(runs) < 2: return None
    best_name, best_pct = best_single_run(runs)
    if not best_name: return None
    best = runs[best_name]

    common = sorted(set(res) & set(best))
    if not common: return None
    t0 = common[0]
    segs = compute_segments(common)
    shapes = make_segment_shapes(t0, segs)

    # Panel 1: Q heatmap
    q_trace = make_q_heatmap(t0, common, [res[t]['q'] for t in common], 'Q')

    # Panel 2: h_ensemble − h_best (видно, где ансамбль отклонился)
    diff_h = [res[t]['h'] - best[t]['h'] for t in common]
    tr_dh = make_line(t0, common, diff_h, 'h_ens − h_best', 'м',
                      color='#d62728', n_out=2000)

    # Panel 3: spread между 8
    spread, n_fix = spread_and_count(runs, common)
    times_sp = sorted(spread)
    if times_sp:
        tr_sp = make_line(t0, times_sp, [spread[t] for t in times_sp],
                          'spread 8 прогонов', 'м',
                          color='#ff7f0e', n_out=2000)
    else:
        tr_sp = None

    # Panel 4: n_fix (сколько прогонов дают Q=1)
    times_nf = sorted(n_fix)
    tr_nf = make_line(t0, times_nf, [n_fix[t] for t in times_nf],
                      'n_fix (из 8)', 'шт',
                      color='#2ca02c', n_out=2000)

    panels = [
        make_panel('Q-value', [q_trace], 'категория', shapes),
        make_panel('h_ensemble − h_best ({})'.format(best_name),
                   [tr_dh], 'м', shapes),
        make_panel('Spread (max−min h по 8 прогонам), м',
                   [tr_sp], 'м', shapes),
        make_panel('n_fix (число прогонов с Q=1)', [tr_nf], 'шт', shapes),
    ]
    return {
        'name': 'C: Ensemble vs Best Single',
        'panels': panels,
        'annotation': {
            'best_run': best_name,
            'best_q1_pct': round(best_pct * 100, 2),
            'n_runs': len(runs),
        },
    }

# ==================== Вкладка B ====================

def build_tab_b(result_pos_path, orig_pos_path, seg_dirs):
    """B: orig Viterbi (без сегментации) vs segmented result.
    Возвращает None, если orig_pos_path не задан.
    """
    if not orig_pos_path or not os.path.exists(orig_pos_path):
        return None
    res = load_pos(result_pos_path)
    orig = load_pos(orig_pos_path)
    if not res or not orig: return None
    common = sorted(set(res) & set(orig))
    if not common: return None
    t0 = common[0]
    segs = compute_segments(common)
    shapes = make_segment_shapes(t0, segs)

    q_trace = make_q_heatmap(t0, common, [res[t]['q'] for t in common], 'Q')

    h_s = [res[t]['h'] for t in common]
    h_o = [orig[t]['h'] for t in common]
    tr_s = make_line(t0, common, h_s, 'segmented', 'h, м',
                     color='#1f77b4', n_out=2000)
    tr_o = make_line(t0, common, h_o, 'orig (no seg)', 'h, м',
                     color='#888888', n_out=2000)

    dh = [h_o[i] - h_s[i] for i in range(len(common))]
    tr_dh = make_line(t0, common, dh, 'dH = orig − segmented', 'м',
                      color='#d62728', n_out=2000)

    panels = [
        make_panel('Q-value', [q_trace], 'категория', shapes),
        make_panel('Height, м', [tr_s, tr_o], 'h, м', shapes),
        make_panel('dH = orig − segmented, м', [tr_dh], 'dH, м', shapes),
    ]
    return {
        'name': 'B: Orig vs Segmented',
        'panels': panels,
        'annotation': {
            'n_common': len(common),
            'dh_stats': stats_line(dh),
        },
    }


# ==================== Вкладка D (GrafNav) ====================

def build_tab_d(result_pos_path, grafnav_path):
    """D: our result.pos vs GrafNav .xyz.
    GrafNav может быть недоступен -- тогда None.
    """
    if not grafnav_path or not os.path.exists(grafnav_path):
        return None
    res = load_pos(result_pos_path)
    graf = load_grafnav(grafnav_path)
    if not res or not graf: return None
    common = sorted(set(res) & set(graf))
    if not common: return None
    t0 = common[0]
    segs = compute_segments(common)
    shapes = make_segment_shapes(t0, segs)

    q_trace = make_q_heatmap(t0, common, [res[t]['q'] for t in common], 'Q')

    # (панель "h ours vs GrafNav" удалена -- линии сливаются, разница 0.75 м
    #  на фоне диапазона 1000 м; смотреть d3D/dH/dHoriz)

    # Три метрики: d3D, dH signed, dHoriz
    d3d = []; dh_sgn = []; dhor = []
    for t in common:
        a = res[t]; b = graf[t]
        R = 6371000.0
        lat_mid = math.radians((a['lat'] + b[0]) / 2.0)
        dlat = math.radians(b[0] - a['lat'])
        dlon = math.radians(b[1] - a['lon'])
        dn = dlat * R
        de = dlon * R * math.cos(lat_mid)
        dh = b[2] - a['h']
        d3d.append(math.sqrt(dn*dn + de*de + dh*dh))
        dh_sgn.append(dh)
        dhor.append(math.sqrt(dn*dn + de*de))

    tr_d3d = make_line(t0, common, d3d, 'd3D', 'м',
                       color='#d62728', n_out=2000)
    tr_dh  = make_line(t0, common, dh_sgn, 'dH (signed)', 'м',
                       color='#9467bd', n_out=2000)
    tr_dhor = make_line(t0, common, dhor, 'dHoriz', 'м',
                       color='#8c564b', n_out=2000)

    panels = [
        make_panel('Q-value', [q_trace], 'категория', shapes),
        make_panel('d3D (|our − GrafNav|), м', [tr_d3d], 'м', shapes),
        make_panel('dH (signed): our − GrafNav, м', [tr_dh], 'м', shapes),
        make_panel('dHoriz, м', [tr_dhor], 'м', shapes),
    ]
    return {
        'name': 'D: Our vs GrafNav',
        'panels': panels,
        'annotation': {
            'n_common': len(common),
            'd3d_stats': stats_line(d3d),
            'dh_stats': stats_line(dh_sgn),
            'dhor_stats': stats_line(dhor),
        },
    }


# ==================== Сборка summary ====================

def build_summary(result_pos, seg_dirs, orig=None, grafnav=None):
    """Собирает 4 вкладки (A/C обязательно, B/D -- опционально)."""
    tabs = []
    a = build_tab_a(result_pos, seg_dirs)
    if a: tabs.append(a)
    b = build_tab_b(result_pos, orig, seg_dirs)
    if b: tabs.append(b)
    c = build_tab_c(result_pos, seg_dirs)
    if c: tabs.append(c)
    d = build_tab_d(result_pos, grafnav)
    if d: tabs.append(d)
    meta = {
        'result_pos': os.path.abspath(result_pos),
        'seg_dirs': [os.path.abspath(s) for s in (seg_dirs or [])],
        'orig_pos': os.path.abspath(orig) if orig else None,
        'grafnav': os.path.abspath(grafnav) if grafnav else None,
        'n_tabs': len(tabs),
        'generated': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
    }
    return {'meta': meta, 'tabs': tabs}


def to_json(data):
    """JSON-сериализация с поддержкой datetime."""
    return json.dumps(data, default=str, ensure_ascii=False)


# ==================== Fix: кириллическая о в tr_dhor ====================

# ==================== Sanitize NaN/Inf ====================

def sanitize(obj):
    """Рекурсивно заменяет NaN/Inf на None (для JSON)."""
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj
    if isinstance(obj, dict):
        return {k: sanitize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [sanitize(x) for x in obj]
    return obj


# ==================== HTML rendering ====================

def render_html(data_json, title, out_path, standalone=False):
    """Генерирует HTML из шаблона и данных."""
    tmpl_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             'plot_summary_template.html')
    with open(tmpl_path) as f:
        tpl = f.read()

    plotly_path = os.path.expanduser('~/gnss_experiment/bin/plotly.min.js')
    if standalone:
        if not os.path.exists(plotly_path):
            print('ERROR: {} не найден (--standalone требует plotly.min.js)'.format(
                  plotly_path), file=sys.stderr)
            sys.exit(1)
        with open(plotly_path) as f:
            plotly_lib = '<script>' + f.read() + '</script>'
    else:
        plotly_uri = 'file://' + os.path.abspath(plotly_path)
        plotly_lib = '<script src="' + plotly_uri + '"></script>'

    meta_obj = json.loads(data_json)['meta']
    meta_str = 'result: {}'.format(meta_obj['result_pos'])
    if meta_obj.get('seg_dirs'):
        meta_str += ' | seg dirs: {}'.format(len(meta_obj['seg_dirs']))
    if meta_obj.get('grafnav'):
        meta_str += ' | grafnav: yes'
    if meta_obj.get('orig_pos'):
        meta_str += ' | orig: yes'
    meta_str += ' | generated: {}'.format(meta_obj['generated'])

    html = (tpl
            .replace('@@TITLE@@', title)
            .replace('@@PLOTLY_LIB@@', plotly_lib)
            .replace('@@META@@', meta_str)
            .replace('@@DATA@@', data_json))

    with open(out_path, 'w') as f:
        f.write(html)
    return out_path


def find_seg_dirs(result_pos):
    """Автопоиск seg_*/ или ensemble/ рядом с result.pos."""
    base = os.path.dirname(os.path.abspath(result_pos))
    segs = sorted(glob.glob(os.path.join(base, 'seg_*')))
    segs = [s for s in segs if os.path.isdir(s)]
    if segs:
        return segs
    ens = os.path.join(base, 'ensemble')
    if os.path.isdir(ens):
        return [ens]
    return []


# ==================== CLI ====================

def main():
    ap = argparse.ArgumentParser(
        description='plot_summary.py -- HTML-отчёт по одному GNSS-проекту')
    ap.add_argument('result_pos', help='путь к result.pos')
    ap.add_argument('--seg-dir', action='append', default=None,
                    help='seg_N директория (можно указать несколько)')
    ap.add_argument('--orig', default=None,
                    help='orig result.pos (v1.1.x) для вкладки B')
    ap.add_argument('--grafnav', default=None,
                    help='GrafNav .xyz для вкладки D')
    ap.add_argument('--out', default=None,
                    help='путь к HTML (default: рядом с result.pos)')
    ap.add_argument('--standalone', action='store_true',
                    help='вшить plotly.min.js внутрь (для передачи)')
    ap.add_argument('--title', default='GNSS Report',
                    help='заголовок отчёта')
    args = ap.parse_args()

    if not os.path.exists(args.result_pos):
        print('ERROR: {} не найден'.format(args.result_pos), file=sys.stderr)
        sys.exit(1)


    seg_dirs = args.seg_dir if args.seg_dir else find_seg_dirs(args.result_pos)

    data = build_summary(args.result_pos, seg_dirs,
                         orig=args.orig, grafnav=args.grafnav)
    data_san = sanitize(data)
    data_json = json.dumps(data_san, ensure_ascii=False)

    if args.out:
        out = args.out
    else:
        base = os.path.dirname(os.path.abspath(args.result_pos))
        name = os.path.basename(base)
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        out = os.path.join(base, '{}_{}.html'.format(name, ts))

    render_html(data_json, args.title, out, standalone=args.standalone)

    size_kb = os.path.getsize(out) / 1024.0
    print('OK: {} ({:.1f} KB, {} tabs)'.format(
          out, size_kb, data['meta']['n_tabs']))


if __name__ == '__main__':
    main()
