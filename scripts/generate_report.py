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
    sections = []
    for suite in sorted(grouped):
        label = SUITE_LABELS.get(suite, suite)
        cards = []
        for test_name in sorted(grouped[suite]):
            table = make_table_html(grouped[suite][test_name])
            cards.append(f"<div class='card'><h3>{test_name}</h3>{table}</div>")
        sections.append(f"<section><h2>{label}</h2>{''.join(cards)}</section>")

    body = "".join(sections) if sections else "<p>No benchmark results found.</p>"

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
