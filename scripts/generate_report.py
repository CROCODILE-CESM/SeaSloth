#!/usr/bin/env python3
"""
generate_report.py — Build static HTML benchmark report pages from
results/latest.json (pytest-benchmark's native JSON output).

One table per benchmark function: one row per parameter combination, with
mean/min/max timing and RSS memory (when tracked). No charts beyond the
regridding heatmap and the two per-suite line charts, no narrative — just the
numbers pytest-benchmark already computed.

Output: report/regridding.html, report/crocodash.html, report/mom6_forge.html,
plus report/index.html (a landing page linking to all five report pages).
"""

import json
import math
import re
import sys
from pathlib import Path

from report_common import (
    HEATMAP_CSS,
    LINECHART_CSS,
    NAV_PAGES,
    page_shell,
    publish_results_json,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
RESULTS_FILE = REPO_ROOT / "results" / "latest.json"
REPORT_DIR = REPO_ROOT / "report"

# Sequential blue ramp, light -> dark, low magnitude -> high magnitude.
# github.com/CROCODILE-CESM dataviz palette, "Sequential hue" (light mode).
SEQ_RAMP = [
    "#cde2fb",
    "#b7d3f6",
    "#9ec5f4",
    "#86b6ef",
    "#6da7ec",
    "#5598e7",
    "#3987e5",
    "#2a78d6",
    "#256abf",
    "#1c5cab",
    "#184f95",
    "#104281",
    "#0d366b",
]

SRC_SIZES = ["(300, 300)", "(800, 600)", "(1500, 700)"]
DST_SIZES = ["(150, 150)", "(400, 300)", "(700, 350)"]
N_BOUNDARY = ["1000", "10000", "100000"]


def fmt_time(v):
    if v is None:
        return "n/a"
    if v >= 1:
        return f"{v:.2f} s"
    if v >= 1e-3:
        return f"{v * 1e3:.1f} ms"
    if v >= 1e-6:
        return f"{v * 1e6:.1f} µs"
    return f"{v * 1e9:.1f} ns"


def fmt_mb(v):
    if v is None:
        return "—"
    return f"{v:.1f} MB"


def suite_and_test(fullname):
    """'benchmarks/xesmf/test_weights_generate.py::test_generate_weights[...]'
    -> ('xesmf', 'test_generate_weights')"""
    file_part, _, func_part = fullname.partition("::")
    parts = Path(file_part).parts
    suite = parts[1] if len(parts) > 1 and parts[0] == "benchmarks" else parts[0]
    test_name = func_part.split("[")[0]
    return suite, test_name


def param_label(name):
    """'test_generate_weights[bilinear-src0-dst0]' -> 'bilinear-src0-dst0'"""
    if "[" in name and name.endswith("]"):
        return name[name.index("[") + 1 : -1]
    return "(no params)"


def load_benchmarks():
    if not RESULTS_FILE.exists():
        return []
    with open(RESULTS_FILE) as f:
        data = json.load(f)
    return data.get("benchmarks", [])


def _hex_to_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i : i + 2], 16) for i in (0, 2, 4))


def _rgb_to_hex(rgb):
    return "#" + "".join(f"{c:02x}" for c in rgb)


def _ramp_color(t):
    """t in [0, 1] -> interpolated hex color along SEQ_RAMP (low -> high)."""
    t = max(0.0, min(1.0, t))
    pos = t * (len(SEQ_RAMP) - 1)
    i = min(int(pos), len(SEQ_RAMP) - 2)
    frac = pos - i
    c0, c1 = _hex_to_rgb(SEQ_RAMP[i]), _hex_to_rgb(SEQ_RAMP[i + 1])
    rgb = tuple(round(c0[k] + (c1[k] - c0[k]) * frac) for k in range(3))
    return _rgb_to_hex(rgb)


def _text_color_for(hex_color):
    r, g, b = _hex_to_rgb(hex_color)
    luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255
    return "#0b0b0b" if luminance > 0.55 else "#ffffff"


def _normalize_log(v, vmin, vmax):
    if vmax <= vmin or v is None:
        return 0.5
    lv = math.log10(max(v, 1e-9))
    lmin, lmax = math.log10(max(vmin, 1e-9)), math.log10(max(vmax, 1e-9))
    return (lv - lmin) / (lmax - lmin)


def _size_label(s):
    """'(300, 300)' -> '300×300'; '10000' -> '10K'"""
    m = re.match(r"\((\d+), (\d+)\)", s)
    if m:
        return f"{m.group(1)}×{m.group(2)}"
    n = int(s)
    return f"{n // 1000}K" if n >= 1000 else str(n)


_REGRID_ID_RE = re.compile(
    r"^(?:(?P<method>[a-z0-9_]+)-)?"
    r"src\((?P<src>\d+, \d+)\)-"
    r"(?:dst\((?P<dst>\d+, \d+)\)|n(?P<n>\d+))"
    r"(?:-t(?P<ntime>\d+))?$"
)


def _parse_regrid_id(name):
    """Extract (method, src, dst_or_n, ntime) from a regrid benchmark's pytest id.
    Any field not present in the id comes back as None. src/dst come back
    parenthesized ("(300, 300)") to match SRC_SIZES/DST_SIZES; n comes back bare
    to match N_BOUNDARY."""
    inner = name[name.index("[") + 1 : -1]
    m = _REGRID_ID_RE.match(inner)
    if not m:
        return None, None, None, None
    dst_or_n = f"({m.group('dst')})" if m.group("dst") else m.group("n")
    return (
        m.group("method"),
        f"({m.group('src')})" if m.group("src") else None,
        dst_or_n,
        m.group("ntime"),
    )


def _heatmap_grid(bm_list, method_filter, ntime_filter):
    """dict[(src, col)] -> mean seconds, for entries matching the given filters."""
    grid = {}
    for bm in bm_list:
        method, src, col, ntime = _parse_regrid_id(bm["name"])
        if src is None or col is None:
            continue
        if method_filter is not None and method != method_filter:
            continue
        if ntime_filter is not None and ntime != ntime_filter:
            continue
        grid[(src, col)] = bm["stats"]["mean"]
    return grid


def _render_heatmap_panel(title, grid, col_order, vmin, vmax):
    header = "".join(f"<th>{_size_label(c)}</th>" for c in col_order)
    rows_html = []
    for src in SRC_SIZES:
        cells = []
        for col in col_order:
            v = grid.get((src, col))
            if v is None:
                cells.append("<td class='hm-empty'>—</td>")
                continue
            color = _ramp_color(_normalize_log(v, vmin, vmax))
            text_color = _text_color_for(color)
            cells.append(
                f"<td class='hm-cell' style='background:{color};color:{text_color}'>"
                f"{fmt_time(v)}</td>"
            )
        rows_html.append(f"<tr><th>{_size_label(src)}</th>{''.join(cells)}</tr>")
    return f"""
        <div class="hm-panel">
          <h4>{title}</h4>
          <table class="heatmap"><thead><tr><th></th>{header}</tr></thead>
          <tbody>{''.join(rows_html)}</tbody></table>
        </div>"""


def build_regrid_heatmaps(grouped):
    """One consolidated 'source size x destination size -> time' visual covering
    all six xESMF/ESMF weight-generation and apply benchmarks, instead of six
    separate tables. Fixes method='bilinear' (and ntime=1 where applicable) so
    each panel is a plain 3x3 grid; every other parameter combination is still
    available in the detailed tables below."""
    panels = []

    def grid_for(suite, test_name, method_filter, ntime_filter):
        rows = grouped.get(suite, {}).get(test_name, [])
        return _heatmap_grid(rows, method_filter, ntime_filter) if rows else {}

    grid_to_grid = [
        (
            "xESMF — weight generation",
            grid_for("xesmf", "test_generate_weights", "bilinear", None),
            DST_SIZES,
        ),
        (
            "ESMF — weight generation",
            grid_for("esmf", "test_generate_weights", "bilinear", None),
            DST_SIZES,
        ),
        ("xESMF — apply", grid_for("xesmf", "test_apply", "bilinear", "1"), DST_SIZES),
        ("ESMF — apply", grid_for("esmf", "test_apply", "bilinear", "1"), DST_SIZES),
    ]
    grid_to_boundary = [
        (
            "xESMF — weight generation (OBC boundary)",
            grid_for("xesmf", "test_generate_weights_locstream", "bilinear", None),
            N_BOUNDARY,
        ),
        (
            "xESMF — apply (OBC boundary)",
            grid_for("xesmf", "test_apply_locstream", None, "1"),
            N_BOUNDARY,
        ),
    ]

    all_values = [
        v for _, grid, _ in (grid_to_grid + grid_to_boundary) for v in grid.values()
    ]
    if not all_values:
        return ""
    vmin, vmax = min(all_values), max(all_values)

    def render_group(group_title, group_subtitle, panel_specs):
        panels_html = "".join(
            _render_heatmap_panel(title, grid, cols, vmin, vmax)
            for title, grid, cols in panel_specs
            if grid
        )
        if not panels_html:
            return ""
        return f"""
      <div class="hm-group">
        <h3>{group_title}</h3>
        <p class="hm-group-sub">{group_subtitle}</p>
        <div class="hm-grid">{panels_html}</div>
      </div>"""

    body = render_group(
        "Grid → grid",
        "Rows: source grid size. Columns: destination grid size. bilinear method, single timestep.",
        grid_to_grid,
    ) + render_group(
        "Grid → boundary (OBC pattern)",
        "Rows: source grid size. Columns: number of boundary points. bilinear method, single timestep.",
        grid_to_boundary,
    )
    if not body:
        return ""

    legend_stops = ", ".join(SEQ_RAMP)
    return f"""
    <section id="regrid-cost">
      <h2>Regridding cost — source size × destination size → time</h2>
      <p class="hm-legend-label">
        <span class="hm-legend-bar" style="background:linear-gradient(to right, {legend_stops})"></span>
        <span>{fmt_time(vmin)}</span> &rarr; <span>{fmt_time(vmax)}</span> (log scale)
      </p>
      {body}
    </section>"""


def build_tables(benchmarks):
    """Group benchmarks by suite, then by test function. Returns nested dict."""
    grouped = {}
    for bm in benchmarks:
        suite, test_name = suite_and_test(bm["fullname"])
        grouped.setdefault(suite, {}).setdefault(test_name, []).append(bm)
    return grouped


def _linechart_svg(points, y_fmt=fmt_time, color="#2a78d6", width=480, height=220):
    """points: list of (x_label, y_value), sorted ascending by the underlying
    parameter. Renders a single-series line chart on a log-scale y axis with
    direct value labels — no charting library, plain inline SVG."""
    pad_l, pad_r, pad_t, pad_b = 46, 20, 24, 34
    plot_w = width - pad_l - pad_r
    plot_h = height - pad_t - pad_b

    values = [v for _, v in points]
    vmin, vmax = min(values), max(values)
    n = len(points)

    def x_at(i):
        return pad_l + (i / (n - 1) if n > 1 else 0.5) * plot_w

    def y_at(v):
        t = _normalize_log(v, vmin, vmax)
        return pad_t + (1 - t) * plot_h

    coords = [(x_at(i), y_at(v)) for i, (_, v) in enumerate(points)]
    poly = " ".join(f"{x:.1f},{y:.1f}" for x, y in coords)

    gridlines = "".join(
        f"<line x1='{pad_l}' y1='{pad_t + f * plot_h:.1f}' "
        f"x2='{pad_l + plot_w}' y2='{pad_t + f * plot_h:.1f}' "
        f"stroke='#e1e0d9' stroke-width='1'/>"
        for f in (0.0, 0.25, 0.5, 0.75, 1.0)
    )

    labels = "".join(
        f"<text x='{x:.1f}' y='{height - pad_b + 18}' text-anchor='middle' "
        f"class='lc-axis'>{points[i][0]}</text>"
        for i, (x, _) in enumerate(coords)
    )

    points_html = "".join(
        f"<circle cx='{x:.1f}' cy='{y:.1f}' r='4' fill='{color}'>"
        f"<title>{points[i][0]}: {y_fmt(points[i][1])}</title></circle>"
        f"<text x='{x:.1f}' y='{y - 10:.1f}' text-anchor='middle' class='lc-value'>"
        f"{y_fmt(points[i][1])}</text>"
        for i, (x, y) in enumerate(coords)
    )

    return f"""
    <svg class="linechart" viewBox="0 0 {width} {height}" role="img"
         aria-label="Line chart, log scale, of timing across parameter values">
      {gridlines}
      <polyline points="{poly}" fill="none" stroke="{color}" stroke-width="2"/>
      {points_html}
      {labels}
    </svg>"""


# test_topo.py fixes these at grid-construction time; mirrored here to label
# the x-axis by point count rather than raw domain degrees.
GEBCO_RES_DEG = 1 / 240  # GEBCO_2024 native resolution (15 arcsec)
TOPO_DST_RES_DEG = 0.1  # destination Grid(..., resolution=0.1) in test_topo.py


def _fmt_count(n):
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.0f}K"
    return str(n)


def build_topo_linechart(grouped):
    """Topo (Topo.set_from_dataset) cost vs. domain size — a natural sweep
    (5/10/20/40 deg) better read as a trend line than a table row-by-row.
    Labeled by source (GEBCO)/destination point count, since that's the
    actual cost driver, not the domain size in degrees."""
    rows = grouped.get("mom6_forge", {}).get("test_set_from_dataset", [])
    if not rows:
        return ""
    pairs = sorted(
        (
            (r["params"]["domain_deg"], r["stats"]["mean"])
            for r in rows
            if r.get("params")
        ),
        key=lambda p: p[0],
    )
    if len(pairs) < 2:
        return ""

    def label_for(domain_deg):
        src_pts = round(domain_deg / GEBCO_RES_DEG) ** 2
        dst_pts = round(domain_deg / TOPO_DST_RES_DEG) ** 2
        return f"{_fmt_count(src_pts)}→{_fmt_count(dst_pts)}"

    points = [(label_for(deg), mean) for deg, mean in pairs]
    svg = _linechart_svg(points)
    return f"""
        <div class="card">
          <h3>test_set_from_dataset — time vs. grid size</h3>
          <p class="lc-sub">x-axis: GEBCO source points &rarr; destination points (fixed 0.1&deg; destination resolution)</p>
          {svg}
        </div>"""


def build_obc_linechart(grouped):
    """OBC (process_obc_conditions REGRID+MERGE) cost vs. regrid_step — total
    date range and data volume are fixed across the sweep, so this shows the
    per-chunk-count overhead directly."""
    rows = grouped.get("crocodash", {}).get("test_regrid_and_merge", [])
    if not rows:
        return ""
    pairs = sorted(
        (
            (r["params"]["step_days"], r["stats"]["mean"])
            for r in rows
            if r.get("params")
        ),
        key=lambda p: p[0],
    )
    if len(pairs) < 2:
        return ""
    points = [(f"{step}d", mean) for step, mean in pairs]
    svg = _linechart_svg(points, color="#1baf7a")
    return f"""
        <div class="card">
          <h3>test_regrid_and_merge — time vs. regrid_step</h3>
          <p class="lc-sub">x-axis: regrid chunk size in days (fixed 30-day total date range)</p>
          {svg}
        </div>"""


def make_table_html(rows):
    has_rss = any(r.get("extra_info", {}).get("rss_mb") is not None for r in rows)
    header = "<tr><th>Params</th><th>Mean</th><th>Min</th><th>Max</th><th>Rounds</th>"
    if has_rss:
        header += "<th>RSS</th>"
    header += "</tr>"

    body_rows = []
    for r in sorted(rows, key=lambda r: r["name"]):
        stats = r["stats"]
        cells = (
            f"<td>{param_label(r['name'])}</td>"
            f"<td>{fmt_time(stats.get('mean'))}</td>"
            f"<td>{fmt_time(stats.get('min'))}</td>"
            f"<td>{fmt_time(stats.get('max'))}</td>"
            f"<td>{stats.get('rounds', '—')}</td>"
        )
        if has_rss:
            cells += f"<td>{fmt_mb(r.get('extra_info', {}).get('rss_mb'))}</td>"
        body_rows.append(f"<tr>{cells}</tr>")

    return f"<table>{header}{''.join(body_rows)}</table>"


# suite -> (chart builder, name of the test function the chart replaces).
# The table for that test is skipped only if the chart actually rendered
# (needs >=2 data points) — if there's not enough data yet, fall back to
# the table rather than silently dropping the one data point that exists.
LINECHART_BY_SUITE = {
    "mom6_forge": (build_topo_linechart, "test_set_from_dataset"),
    "crocodash": (build_obc_linechart, "test_regrid_and_merge"),
}

FOOTER = "Generated by scripts/generate_report.py"


def build_suite_cards(grouped, suite):
    """Chart (if it renders) + a table per test function not covered by that
    chart, for a single suite — the shared body of the crocodash/mom6_forge
    pages."""
    cards = []
    charted_test = None
    if suite in LINECHART_BY_SUITE:
        builder, charted_test = LINECHART_BY_SUITE[suite]
        chart = builder(grouped)
        if chart:
            cards.append(chart)
        else:
            charted_test = None
    for test_name in sorted(grouped.get(suite, {})):
        if test_name == charted_test:
            continue
        table = make_table_html(grouped[suite][test_name])
        cards.append(f"<div class='card'><h3>{test_name}</h3>{table}</div>")
    return "".join(cards)


def build_regridding_page(grouped):
    heatmaps = build_regrid_heatmaps(grouped)
    body = (
        heatmaps or "<section><p>No regridding benchmark results found.</p></section>"
    )
    return page_shell(
        "regridding.html",
        "SeaSloth — Regridding",
        "xESMF/ESMF weight generation + apply cost, one-time snapshot on Derecho/GLADE.",
        body,
        FOOTER,
        extra_css=HEATMAP_CSS,
    )


def build_crocodash_page(grouped):
    cards = build_suite_cards(grouped, "crocodash")
    body = (
        f"<section><h2>CrocoDash</h2>{cards}</section>"
        if cards
        else "<section><p>No CrocoDash benchmark results found.</p></section>"
    )
    return page_shell(
        "crocodash.html",
        "SeaSloth — CrocoDash",
        "OBC forcing pipeline (regrid + merge) benchmarks, one-time snapshot on Derecho/GLADE.",
        body,
        FOOTER,
        extra_css=LINECHART_CSS,
    )


def build_mom6_forge_page(grouped):
    cards = build_suite_cards(grouped, "mom6_forge")
    body = (
        f"<section><h2>mom6_forge</h2>{cards}</section>"
        if cards
        else "<section><p>No mom6_forge benchmark results found.</p></section>"
    )
    return page_shell(
        "mom6_forge.html",
        "SeaSloth — mom6_forge",
        "Bathymetry pipeline (Topo.set_from_dataset) benchmarks, one-time snapshot on Derecho/GLADE.",
        body,
        FOOTER,
        extra_css=LINECHART_CSS,
    )


LANDING_DESCRIPTIONS = {
    "regridding.html": "xESMF/ESMF weight generation + apply cost across grid sizes.",
    "crocodash.html": "OBC forcing pipeline (regrid + merge) cost vs. chunk size.",
    "mom6_forge.html": "Bathymetry pipeline (Topo.set_from_dataset) cost vs. grid size.",
    "health.html": "Daily data-source reachability + validate_function checks.",
    "mom6_scaling.html": "MOM6 NTASKS_OCN strong-scaling sweep on Derecho.",
}


def build_index_page():
    """Landing page — no benchmark content of its own, just a card per report
    linking out to it (plus its raw JSON, for anything that wants to consume
    the data programmatically). Regenerated every run so it's never missing
    a page."""
    cards = "".join(
        f"<div class='card'><h3><a href='{href}'>{label}</a></h3>"
        f"<p>{LANDING_DESCRIPTIONS[href]}"
        + (f" <a href='{json_name}'>[JSON]</a>" if json_name else "")
        + "</p></div>"
        for href, label, json_name in NAV_PAGES
        if href in LANDING_DESCRIPTIONS
    )
    body = f"<section><h2>Reports</h2>{cards}</section>"
    return page_shell(
        "index.html",
        "SeaSloth",
        "One-time perf snapshot for parts of the CROC ocean modeling ecosystem "
        "that don&rsquo;t change commit-to-commit.",
        body,
        FOOTER,
    )


def main():
    benchmarks = load_benchmarks()
    if not benchmarks:
        print(
            f"No benchmarks found in {RESULTS_FILE}. Run scripts/run_benchmarks.sh first.",
            file=sys.stderr,
        )

    grouped = build_tables(benchmarks)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    pages = {
        "index.html": build_index_page(),
        "regridding.html": build_regridding_page(grouped),
        "crocodash.html": build_crocodash_page(grouped),
        "mom6_forge.html": build_mom6_forge_page(grouped),
    }
    for name, html in pages.items():
        (REPORT_DIR / name).write_text(html)
    publish_results_json(RESULTS_FILE, REPORT_DIR)
    print(f"Report pages written to {REPORT_DIR}: {', '.join(pages)}")


if __name__ == "__main__":
    main()
