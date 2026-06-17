#!/usr/bin/env python3
"""
generate_report.py — Build a standalone HTML benchmark report from ASV result JSONs.

Shows bar charts per benchmark class (parameters on X-axis, last param dimension as
color groups), without commit-timeline context. Output: .asv/html/report.html
"""

import base64
import io
import itertools
import json
import math
import os
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

REPO_ROOT = Path(__file__).resolve().parent.parent
RESULTS_DIR = REPO_ROOT / "results"
OUTPUT_FILE = REPO_ROOT / ".asv" / "html" / "report.html"

UNIT_LABELS = {
    "time": "seconds",
    "track_rss": "MB",
}

SUITE_LABELS = {
    "xesmf": "xESMF / ESMF",
    "mom6_forge": "mom6_forge",
    "crocodash": "CrocoDash",
    "e2e": "End-to-End",
}


def short(label):
    """Strip quotes and simplify tuple-like labels."""
    label = label.strip("'\"")
    label = label.replace("(", "").replace(")", "").replace(" ", "")
    return label


def infer_unit(bench_key):
    if ".track_rss" in bench_key:
        return "MB"
    if ".time_" in bench_key:
        return "s"
    return ""


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
                if any(v is not None and not (isinstance(v, float) and math.isnan(v)) for v in results):
                    latest[key] = (results, params)

    return latest


def make_chart(bench_key, results, params):
    """
    Create a grouped bar chart for one benchmark.

    Layout: last param dimension = color groups, product of all other param
    dimensions = X-axis categories. Returns base64-encoded PNG or None.
    """
    combos = list(itertools.product(*params))
    if len(results) != len(combos):
        return None

    valid_pairs = [
        (c, r)
        for c, r in zip(combos, results)
        if r is not None and not (isinstance(r, float) and math.isnan(r))
    ]
    if not valid_pairs:
        return None

    unit = infer_unit(bench_key)

    if len(params) == 1:
        labels = [short(c[0]) for c, _ in valid_pairs]
        values = [r for _, r in valid_pairs]

        fig, ax = plt.subplots(figsize=(max(5, len(labels) * 0.9 + 1), 4))
        ax.bar(range(len(labels)), values, color="#4c78a8", width=0.6)
        ax.set_xticks(range(len(labels)))
        ax.set_xticklabels(labels, rotation=25, ha="right", fontsize=9)
        ax.set_ylabel(unit)
        ax.yaxis.grid(True, alpha=0.35)
        ax.set_axisbelow(True)

    else:
        # Group by last param dimension; X = cartesian product of remaining dims
        group_vals = params[-1]
        x_params = params[:-1]
        x_combos = list(itertools.product(*x_params))
        n_x = len(x_combos)
        n_g = len(group_vals)

        # Build lookup: (x_combo, group_val) -> result
        lookup = {}
        for combo, r in valid_pairs:
            lookup[(combo[:-1], combo[-1])] = r

        colors = plt.cm.tab10(np.linspace(0, 0.9, n_g))
        width = min(0.8 / n_g, 0.35)
        fig_width = max(6, n_x * n_g * (width + 0.05) * 1.5 + 2)
        fig, ax = plt.subplots(figsize=(fig_width, 4))

        for i, g in enumerate(group_vals):
            offsets = [j + i * width for j in range(n_x)]
            values = [lookup.get((xc, g), np.nan) for xc in x_combos]
            ax.bar(offsets, values, width=width, label=short(g), color=colors[i], alpha=0.88)

        center = (n_g - 1) * width / 2
        x_labels = [" × ".join(short(v) for v in xc) for xc in x_combos]
        ax.set_xticks([j + center for j in range(n_x)])
        ax.set_xticklabels(x_labels, rotation=30, ha="right", fontsize=8)
        ax.set_ylabel(unit)
        ax.legend(fontsize=8, framealpha=0.7)
        ax.yaxis.grid(True, alpha=0.35)
        ax.set_axisbelow(True)

    plt.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=130, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode()


def bench_display_name(bench_key):
    """Turn 'xesmf.bench_regridder_creation.RegridderCreation.time_create_regridder'
    into a readable title."""
    parts = bench_key.split(".")
    # parts: [suite, module, class, method]
    if len(parts) >= 4:
        return f"{parts[2]}.{parts[3]}"
    return bench_key


def param_table_html(params):
    """Render param dimensions as a compact description."""
    rows = []
    for i, p in enumerate(params):
        vals = ", ".join(short(v) for v in p)
        rows.append(f"<code>param[{i}]:</code> {vals}")
    return "<br>".join(rows)


def build_html(all_results):
    # Group by suite
    by_suite = {}
    for key, (results, params) in sorted(all_results.items()):
        suite = key.split(".")[0]
        by_suite.setdefault(suite, {})[key] = (results, params)

    sections = []
    for suite, benchmarks in sorted(by_suite.items()):
        suite_label = SUITE_LABELS.get(suite, suite)
        cards = []
        for key, (results, params) in sorted(benchmarks.items()):
            b64 = make_chart(key, results, params)
            if b64 is None:
                continue
            name = bench_display_name(key)
            param_info = param_table_html(params)
            cards.append(
                f"""
        <div class="card">
          <h3>{name}</h3>
          <div class="params">{param_info}</div>
          <img src="data:image/png;base64,{b64}" alt="{name}">
        </div>"""
            )

        if not cards:
            continue

        sections.append(
            f"""
    <section>
      <h2>{suite_label}</h2>
      <div class="grid">{"".join(cards)}
      </div>
    </section>"""
        )

    body = "\n".join(sections) if sections else "<p>No benchmark results found.</p>"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>CrocoScope Benchmark Report</title>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
         margin: 0; padding: 0; background: #f5f6fa; color: #222; }}
  header {{ background: #1a3a5c; color: #fff; padding: 1.5rem 2rem; }}
  header h1 {{ margin: 0 0 0.25rem; font-size: 1.6rem; }}
  header p  {{ margin: 0; opacity: 0.75; font-size: 0.9rem; }}
  section {{ padding: 1.5rem 2rem 0.5rem; }}
  section h2 {{ font-size: 1.2rem; border-bottom: 2px solid #c8d6e5;
                padding-bottom: 0.4rem; margin-bottom: 1rem; color: #1a3a5c; }}
  .grid {{ display: flex; flex-wrap: wrap; gap: 1.25rem; }}
  .card {{ background: #fff; border-radius: 8px; padding: 1rem 1.25rem;
           box-shadow: 0 1px 4px rgba(0,0,0,0.1); max-width: 700px; }}
  .card h3 {{ margin: 0 0 0.4rem; font-size: 0.95rem; color: #333;
              font-family: 'SFMono-Regular', Consolas, monospace; }}
  .params {{ font-size: 0.78rem; color: #666; margin-bottom: 0.6rem; line-height: 1.5; }}
  .params code {{ color: #888; }}
  .card img {{ max-width: 100%; height: auto; display: block; }}
  footer {{ padding: 1.5rem 2rem; font-size: 0.8rem; color: #888; }}
  footer a {{ color: #4c78a8; }}
</style>
</head>
<body>
<header>
  <h1>CrocoScope Benchmark Report</h1>
  <p>Performance snapshot — benchmarks run on Derecho/GLADE.
     <a href="index.html" style="color:#9fc3e8">View commit history &rarr;</a></p>
</header>
{body}
<footer>
  Generated by <code>scripts/generate_report.py</code> &mdash;
  <a href="https://github.com/CROCODILE-CESM/CrocoScope">CrocoScope</a>
</footer>
</body>
</html>
"""


def main():
    print("Loading benchmark results...")
    all_results = load_all_results()
    if not all_results:
        print("No results found in results/. Nothing to plot.", file=sys.stderr)
        sys.exit(0)

    print(f"Found {len(all_results)} benchmarks with data.")

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    html = build_html(all_results)
    OUTPUT_FILE.write_text(html)
    print(f"Report written to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
