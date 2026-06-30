#!/usr/bin/env python3
"""
generate_health_page.py — Build a standalone data-access health status page.

Reads ASV result JSONs from results/ and produces .asv/html/health.html — a
dedicated page showing pass/fail status for every registered CrocoDash data
source and its documentation URL.

Run after asv publish (or standalone) to regenerate:
    python scripts/generate_health_page.py
"""

import itertools
import json
import math
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
RESULTS_DIR = REPO_ROOT / "results"
OUTPUT_FILE = REPO_ROOT / ".asv" / "html" / "health.html"

_HEALTH_KEYS = {
    "accessible": "crocodash.bench_raw_data_access.DataAccessHealth.track_accessible",
    "timing": "crocodash.bench_raw_data_access.DataAccessHealth.time_validate",
    "link": "crocodash.bench_raw_data_access.DataAccessLinkCheck.track_link_ok",
}


def fmt_time(v):
    if v is None:
        return "n/a"
    if v >= 60:
        return f"{v/60:.1f} min"
    if v >= 1:
        return f"{v:.1f} s"
    if v >= 1e-3:
        return f"{v*1e3:.0f} ms"
    if v >= 1e-6:
        return f"{v*1e6:.0f} μs"
    return f"{v*1e9:.0f} ns"


def load_all_results():
    """Load the most recent non-null value for each benchmark across all result files."""
    file_data = []
    for machine_dir in sorted(RESULTS_DIR.iterdir()):
        if not machine_dir.is_dir():
            continue
        for f in sorted(machine_dir.glob("*.json")):
            if f.name == "machine.json":
                continue
            try:
                with open(f) as fh:
                    d = json.load(fh)
                file_data.append((d.get("date", 0), d))
            except Exception:
                pass

    file_data.sort(key=lambda x: x[0])

    latest = {}
    for _date, d in file_data:
        for key, value in d.get("results", {}).items():
            if isinstance(value, list) and value[0] is not None:
                results = value[0]
                params = value[1]
                if any(
                    v is not None and not (isinstance(v, float) and math.isnan(v))
                    for v in results
                ):
                    latest[key] = (results, params)

    return latest


def _parse_pm(param_str):
    """'('glorys', 'get_data')' → ('glorys', 'get_data')"""
    m = re.findall(r"'([^']+)'", param_str)
    return (m[0], m[1]) if len(m) >= 2 else (param_str, "")


def _yn(val, good=1.0):
    """Return coloured Yes/No HTML span, or a dash if unknown."""
    if val is None:
        return '<span style="color:#999">—</span>'
    if val == good:
        return '<span class="ok">Yes</span>'
    return '<span class="fail">No</span>'


def build_health_table(all_results):
    """Return (rows, ok_count, total_count) where rows is list of dicts."""
    h_key = _HEALTH_KEYS["accessible"]
    t_key = _HEALTH_KEYS["timing"]
    l_key = _HEALTH_KEYS["link"]

    if h_key not in all_results:
        return None, 0, 0

    h_results, h_params = all_results[h_key]
    h_combos = list(itertools.product(*h_params))

    time_lookup = {}
    if t_key in all_results:
        t_results, t_params = all_results[t_key]
        for combo, t in zip(itertools.product(*t_params), t_results):
            time_lookup[combo] = t

    link_lookup = {}
    if l_key in all_results:
        l_results, l_params = all_results[l_key]
        for combo, lv in zip(itertools.product(*l_params), l_results):
            prod_name = combo[0].strip("'\"")
            link_lookup[prod_name] = lv

    rows = []
    for combo, h in zip(h_combos, h_results):
        product, method = _parse_pm(combo[0])
        t = time_lookup.get(combo)
        valid_t = (
            t if (t is not None and not (isinstance(t, float) and math.isnan(t))) else None
        )
        link_val = link_lookup.get(product)
        ok = h == 1.0 if h is not None else False
        rows.append(
            {
                "product": product,
                "method": method.replace("_", " "),
                "raw_method": method,
                "accessible": h,
                "time": valid_t,
                "link_ok": link_val,
                "ok": ok,
            }
        )

    ok_count = sum(1 for r in rows if r["ok"])
    return rows, ok_count, len(rows)


def _run_timestamp(all_results):
    """Best-effort: return date of the most recent result file, or empty string."""
    h_key = _HEALTH_KEYS["accessible"]
    if h_key not in all_results:
        return ""
    # Load file_data again to find the date
    latest_date = 0
    for machine_dir in sorted(RESULTS_DIR.iterdir()):
        if not machine_dir.is_dir():
            continue
        for f in sorted(machine_dir.glob("*.json")):
            if f.name == "machine.json":
                continue
            try:
                d = json.loads(f.read_text())
                if h_key in d.get("results", {}):
                    ts = d.get("date", 0)
                    if ts > latest_date:
                        latest_date = ts
            except Exception:
                pass
    if not latest_date:
        return ""
    # date is ms since epoch in ASV
    import datetime
    dt = datetime.datetime.utcfromtimestamp(latest_date / 1000)
    return dt.strftime("%Y-%m-%d %H:%M UTC")


def build_html(all_results):
    rows, ok_count, total = build_health_table(all_results)
    timestamp = _run_timestamp(all_results)
    ts_note = f" &mdash; last run {timestamp}" if timestamp else ""

    if rows is None:
        body = "<p>No health data found in <code>results/</code>.</p>"
        status_bar = ""
    else:
        all_ok = ok_count == total
        status_color = "#1a7a3e" if all_ok else "#b30000"
        status_text = (
            "All data sources accessible"
            if all_ok
            else f"{ok_count} of {total} data sources accessible"
        )
        status_bar = f"""
<div class="status-bar" style="background:{status_color}">
  <span class="status-icon">{"✓" if all_ok else "✗"}</span>
  <span>{status_text}</span>
  <span class="ts">{ts_note}</span>
</div>"""

        tr_rows = []
        for i, r in enumerate(rows):
            bg = ' class="alt"' if i % 2 == 0 else ""
            time_html = (
                fmt_time(r["time"])
                if r["time"] is not None
                else '<span style="color:#999">—</span>'
            )
            tr_rows.append(
                f'<tr{bg}>'
                f'<td class="product">{r["product"]}</td>'
                f'<td class="method"><code>{r["raw_method"]}</code></td>'
                f'<td class="check">{_yn(r["accessible"])}</td>'
                f'<td class="check">{_yn(r["link_ok"])}</td>'
                f'<td class="time">{time_html}</td>'
                f"</tr>"
            )

        body = f"""
<table>
  <thead>
    <tr>
      <th>Product</th>
      <th>Access method</th>
      <th>Accessible?</th>
      <th>URL live?</th>
      <th>Validation time</th>
    </tr>
  </thead>
  <tbody>
    {"".join(tr_rows)}
  </tbody>
</table>
<p class="note">
  <b>Accessible?</b> — <code>ProductRegistry.validate_function()</code> called with toy
  arguments; passes if no exception is raised.<br>
  <b>URL live?</b> — HTTP HEAD/GET to the product's registered documentation or
  download link; passes if HTTP 200.<br>
  Benchmarks run on GLADE/Derecho. Results committed to git; this page is
  regenerated by CI on every push to <code>main</code> and daily.
</p>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Data Access Health — SeaSloth</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
         background: #f5f6fa; color: #222; }}
  header {{ background: #1a3a5c; color: #fff; padding: 1.25rem 2rem; display: flex;
            align-items: baseline; gap: 1.5rem; flex-wrap: wrap; }}
  header h1 {{ font-size: 1.4rem; }}
  header a {{ color: #9fc3e8; font-size: 0.88rem; text-decoration: none; }}
  header a:hover {{ text-decoration: underline; }}
  .status-bar {{ display: flex; align-items: center; gap: 1rem;
                 padding: 0.75rem 2rem; color: #fff; font-size: 0.95rem;
                 font-weight: 600; flex-wrap: wrap; }}
  .status-bar .status-icon {{ font-size: 1.3rem; line-height: 1; }}
  .status-bar .ts {{ font-weight: 400; opacity: 0.8; font-size: 0.82rem; margin-left: auto; }}
  main {{ padding: 1.5rem 2rem; max-width: 900px; }}
  table {{ width: 100%; border-collapse: collapse; background: #fff;
           border-radius: 8px; overflow: hidden;
           box-shadow: 0 1px 4px rgba(0,0,0,0.1); font-size: 0.9rem; }}
  thead tr {{ background: #1a3a5c; color: #fff; }}
  thead th {{ padding: 0.6rem 0.75rem; text-align: left; font-weight: 600;
              font-size: 0.83rem; letter-spacing: 0.02em; }}
  th.check, td.check {{ text-align: center; }}
  th.time, td.time {{ text-align: right; font-variant-numeric: tabular-nums; }}
  tbody tr {{ border-bottom: 1px solid #eef0f5; }}
  tbody tr.alt {{ background: #f7f9fc; }}
  tbody tr:hover {{ background: #eef2fb; }}
  td {{ padding: 0.45rem 0.75rem; }}
  td.product {{ font-weight: 600; color: #1a3a5c; white-space: nowrap; }}
  td.method code {{ font-size: 0.82rem; color: #555; background: #eef1f6;
                    padding: 0.15em 0.4em; border-radius: 3px; }}
  .ok  {{ color: #1a7a3e; font-weight: 700; }}
  .fail {{ color: #b30000; font-weight: 700; }}
  p.note {{ margin-top: 1rem; font-size: 0.82rem; color: #666; line-height: 1.6; }}
  p.note code {{ background: #eef1f6; padding: 0.1em 0.35em; border-radius: 3px; }}
  footer {{ padding: 1.25rem 2rem; font-size: 0.78rem; color: #888; }}
  footer a {{ color: #4c78a8; }}
</style>
</head>
<body>
<header>
  <h1>Data Access Health</h1>
  <a href="index.html">&larr; Benchmark report</a>
  <a href="asv_timeline.html">Regression timeline &rarr;</a>
</header>
{status_bar}
<main>
{body}
</main>
<footer>
  Generated by <code>scripts/generate_health_page.py</code> &mdash;
  <a href="https://github.com/CROCODILE-CESM/SeaSloth">SeaSloth</a>
</footer>
</body>
</html>
"""


def main():
    print("Loading benchmark results...")
    all_results = load_all_results()
    if not all_results:
        print("No results found in results/.", file=sys.stderr)
        sys.exit(0)

    h_key = _HEALTH_KEYS["accessible"]
    if h_key not in all_results:
        print("No health data in results/. Run DataAccessHealth benchmarks first.", file=sys.stderr)
        sys.exit(0)

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    html = build_html(all_results)
    OUTPUT_FILE.write_text(html)
    print(f"Health page written to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
