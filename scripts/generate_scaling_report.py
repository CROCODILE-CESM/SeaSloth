#!/usr/bin/env python3
"""
generate_scaling_report.py — Build a static HTML page from results/mom6_scaling.json
(a hand-run MOM6 NTASKS_OCN strong-scaling sweep on Derecho's develop queue).

Not a pytest-benchmark suite — one throughput number per NTASKS_OCN, not repeated
call-timing statistics — so it gets its own JSON schema and its own page rather than
being shoehorned into results/latest.json. Reuses generate_report.py's generic
_linechart_svg/_ramp_color helpers (already schema-agnostic, params -> value).

Output: report/mom6_scaling.html
"""

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
RESULTS_FILE = REPO_ROOT / "results" / "mom6_scaling.json"
OUTPUT_FILE = REPO_ROOT / "report" / "mom6_scaling.html"

sys.path.insert(0, str(Path(__file__).resolve().parent))
from generate_report import _linechart_svg  # noqa: E402


def load_scaling():
    if not RESULTS_FILE.exists():
        return None
    with open(RESULTS_FILE) as f:
        return json.load(f)


def fmt_s(v):
    return f"{v:.1f} s" if v < 60 else f"{v / 60:.1f} min"


def make_table_html(points):
    baseline = min(points, key=lambda p: p["ntasks_ocn"])
    baseline_per_core = baseline["throughput_sim_years_per_day"] / baseline["ntasks_ocn"]

    rows = []
    for p in points:
        per_core = p["throughput_sim_years_per_day"] / p["ntasks_ocn"]
        efficiency = 100.0 * per_core / baseline_per_core
        rows.append(
            f"<tr><td>{p['ntasks_ocn']}</td>"
            f"<td>{p['throughput_sim_years_per_day']:.2f}</td>"
            f"<td>{fmt_s(p['tot_run_time_s'])}</td>"
            f"<td>{p['ocn_cost_pe_hrs']:.1f}</td>"
            f"<td>{efficiency:.0f}%</td></tr>"
        )
    return (
        "<table><tr><th>NTASKS_OCN</th><th>Throughput (sim-years/day)</th>"
        f"<th>Total Run Time</th><th>OCN Cost (pe-hrs/sim-year)</th>"
        f"<th>Parallel Efficiency (vs N={baseline['ntasks_ocn']})</th></tr>"
        f"{''.join(rows)}</table>"
    )


def build_html(data):
    if not data or not data.get("points"):
        body = "<p>No scaling results found.</p>"
        meta = ""
    else:
        points = sorted(data["points"], key=lambda p: p["ntasks_ocn"])
        chart_points = [
            (str(p["ntasks_ocn"]), p["throughput_sim_years_per_day"]) for p in points
        ]
        chart = _linechart_svg(
            chart_points, y_fmt=lambda v: f"{v:.1f} y/day", color="#2a78d6"
        )
        table = make_table_html(points)
        meta = (
            f"<p class='lc-sub'>Grid: {data.get('grid', '?')} &mdash; "
            f"compset: <code>{data.get('compset', '?')}</code> &mdash; "
            f"machine: {data.get('machine', '?')} ({data.get('queue', '?')} queue) &mdash; "
            f"date range: {', '.join(data.get('date_range', []))}</p>"
        )
        body = f"""
    <section>
      <h2>Model Throughput vs. NTASKS_OCN</h2>
      {meta}
      <div class="card">
        <h3>Throughput (simulated years / wallclock day)</h3>
        <p class="lc-sub">x-axis: NTASKS_OCN (log-scale y-axis)</p>
        {chart}
      </div>
      <div class="card">
        <h3>Full results</h3>
        {table}
      </div>
    </section>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>SeaSloth MOM6 Scaling Report</title>
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

  .linechart {{ width: 100%; max-width: 480px; height: auto; display: block; }}
  .lc-sub {{ font-size: 0.75rem; color: #777; margin: -0.4rem 0 0.75rem; }}
  .lc-axis {{ font-size: 9px; fill: #898781; font-family: -apple-system, sans-serif; }}
  .lc-value {{ font-size: 10px; fill: #333; font-variant-numeric: tabular-nums;
               font-family: -apple-system, sans-serif; }}
</style>
</head>
<body>
<header>
  <h1>SeaSloth MOM6 Scaling Report</h1>
  <p>NTASKS_OCN strong-scaling sweep, run by hand on Derecho's develop queue.
     <a href="index.html">&larr; Benchmark report</a></p>
</header>
{body}
<footer>Generated by scripts/generate_scaling_report.py</footer>
</body>
</html>
"""


def main():
    data = load_scaling()
    if not data:
        print(f"No scaling results found in {RESULTS_FILE}.", file=sys.stderr)

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(build_html(data))
    print(f"Scaling report written to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
