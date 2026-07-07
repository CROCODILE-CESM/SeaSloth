#!/usr/bin/env python3
"""
generate_report.py — Build a static HTML benchmark report from results/latest.json
(pytest-benchmark's native JSON output).

One table per benchmark function: one row per parameter combination, with
mean/min/max timing and RSS memory (when tracked). No charts, no narrative —
just the numbers pytest-benchmark already computed.

Output: report/index.html
"""

import json
import math
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
RESULTS_FILE = REPO_ROOT / "results" / "latest.json"
OUTPUT_FILE = REPO_ROOT / "report" / "index.html"

SUITE_LABELS = {
    "xesmf": "xESMF",
    "esmf": "ESMF",
    "mom6_forge": "mom6_forge",
    "crocodash": "CrocoDash",
}

# Sequential blue ramp, light -> dark, low magnitude -> high magnitude.
# github.com/CROCODILE-CESM dataviz palette, "Sequential hue" (light mode).
SEQ_RAMP = [
    "#cde2fb", "#b7d3f6", "#9ec5f4", "#86b6ef", "#6da7ec", "#5598e7",
    "#3987e5", "#2a78d6", "#256abf", "#1c5cab", "#184f95", "#104281", "#0d366b",
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
        ("xESMF — weight generation", grid_for("xesmf", "test_generate_weights", "bilinear", None), DST_SIZES),
        ("ESMF — weight generation", grid_for("esmf", "test_generate_weights", "bilinear", None), DST_SIZES),
        ("xESMF — apply", grid_for("xesmf", "test_apply", "bilinear", "1"), DST_SIZES),
        ("ESMF — apply", grid_for("esmf", "test_apply", "bilinear", "1"), DST_SIZES),
    ]
    grid_to_boundary = [
        ("xESMF — weight generation (OBC boundary)", grid_for("xesmf", "test_generate_weights_locstream", "bilinear", None), N_BOUNDARY),
        ("xESMF — apply (OBC boundary)", grid_for("xesmf", "test_apply_locstream", None, "1"), N_BOUNDARY),
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


def build_html(grouped):
    heatmaps = build_regrid_heatmaps(grouped)

    sections = []
    for suite in sorted(grouped):
        label = SUITE_LABELS.get(suite, suite)
        cards = []
        for test_name in sorted(grouped[suite]):
            table = make_table_html(grouped[suite][test_name])
            cards.append(f"<div class='card'><h3>{test_name}</h3>{table}</div>")
        heading = f"{label} — all parameter combinations" if suite in ("xesmf", "esmf") else label
        sections.append(f"<section><h2>{heading}</h2>{''.join(cards)}</section>")

    body = heatmaps + (
        "".join(sections) if sections else "<p>No benchmark results found.</p>"
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>SeaSloth Benchmark Report</title>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
         margin: 0; padding: 0; background: #f5f6fa; color: #222; }}
  header {{ background: #1a3a5c; color: #fff; padding: 1.5rem 2rem; }}
  header h1 {{ margin: 0 0 0.25rem; font-size: 1.6rem; }}
  header a {{ color: #9fc3e8; }}
  section {{ padding: 1.5rem 2rem 0.5rem; }}
  section h2 {{ font-size: 1.2rem; border-bottom: 2px solid #c8d6e5;
                padding-bottom: 0.4rem; margin-bottom: 1rem; color: #1a3a5c; }}
  .card {{ background: #fff; border-radius: 8px; padding: 1rem 1.25rem;
           box-shadow: 0 1px 4px rgba(0,0,0,0.1); margin-bottom: 1.25rem; overflow-x: auto; }}
  .card h3 {{ margin: 0 0 0.6rem; font-size: 0.95rem; color: #333;
              font-family: 'SFMono-Regular', Consolas, monospace; }}
  table {{ border-collapse: collapse; width: 100%; font-size: 0.85rem; }}
  th, td {{ text-align: right; padding: 0.3rem 0.6rem; }}
  th:first-child, td:first-child {{ text-align: left; }}
  thead th {{ border-bottom: 2px solid #c8d6e5; color: #555; }}
  tbody tr:nth-child(even) {{ background: #f7f9fc; }}
  footer {{ padding: 1.5rem 2rem; font-size: 0.8rem; color: #888; }}

  #regrid-cost {{ background: #fff; border-bottom: 1px solid #dde4ee; }}
  .hm-legend-label {{ display: flex; align-items: center; gap: 0.5rem;
                       font-size: 0.78rem; color: #555; margin: 0 0 1.25rem; }}
  .hm-legend-bar {{ display: inline-block; width: 140px; height: 10px;
                     border-radius: 5px; }}
  .hm-group {{ margin-bottom: 1.5rem; }}
  .hm-group h3 {{ font-size: 0.95rem; color: #333; margin: 0 0 0.15rem; }}
  .hm-group-sub {{ font-size: 0.75rem; color: #777; margin: 0 0 0.75rem; }}
  .hm-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
              gap: 1.25rem; }}
  .hm-panel {{ background: #fff; border-radius: 8px; padding: 0.9rem 1rem;
               box-shadow: 0 1px 4px rgba(0,0,0,0.1); }}
  .hm-panel h4 {{ margin: 0 0 0.6rem; font-size: 0.82rem; color: #333;
                  font-family: 'SFMono-Regular', Consolas, monospace; font-weight: 600; }}
  table.heatmap {{ border-collapse: separate; border-spacing: 3px; width: 100%; }}
  table.heatmap th {{ font-size: 0.68rem; font-weight: 500; color: #777;
                      text-align: center; padding: 0.15rem; }}
  table.heatmap td.hm-cell {{ text-align: center; font-variant-numeric: tabular-nums;
                              font-size: 0.7rem; padding: 0.5rem 0.3rem; border-radius: 4px; }}
  table.heatmap td.hm-empty {{ color: #bbb; text-align: center; }}
</style>
</head>
<body>
<header>
  <h1>SeaSloth Benchmark Report</h1>
  <p>One-time perf snapshot, run by hand on Derecho/GLADE.
     <a href="health.html">Data access health &rarr;</a></p>
</header>
{body}
<footer>Generated by scripts/generate_report.py</footer>
</body>
</html>
"""


def main():
    benchmarks = load_benchmarks()
    if not benchmarks:
        print(f"No benchmarks found in {RESULTS_FILE}. Run scripts/run_benchmarks.sh first.",
              file=sys.stderr)

    grouped = build_tables(benchmarks)
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(build_html(grouped))
    print(f"Report written to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
