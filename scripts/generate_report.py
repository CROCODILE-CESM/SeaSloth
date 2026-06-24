#!/usr/bin/env python3
"""
generate_report.py — Build a standalone HTML benchmark report from ASV result JSONs.

Shows a human-readable narrative summary of key findings, followed by bar charts per
benchmark class (parameters on X-axis, last param dimension as color groups).
Output: .asv/html/index.html
"""

import base64
import io
import itertools
import json
import math
import os
import re
import shutil
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

REPO_ROOT = Path(__file__).resolve().parent.parent
RESULTS_DIR = REPO_ROOT / "results"
OUTPUT_FILE = REPO_ROOT / ".asv" / "html" / "index.html"

UNIT_LABELS = {
    "time": "seconds",
    "track_rss": "MB",
}

SUITE_LABELS = {
    "xesmf": "xESMF / ESMF",
    "mom6_forge": "mom6_forge",
    "crocodash": "CrocoDash",
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
                if any(
                    v is not None and not (isinstance(v, float) and math.isnan(v))
                    for v in results
                ):
                    latest[key] = (results, params)

    return latest


def _lookup(results, params, combo):
    """Return the result value for a specific parameter combination, or None."""
    combos = list(itertools.product(*params))
    for c, r in zip(combos, results):
        if c == combo:
            return r
    return None


def _valid_values(results, params):
    """Return list of (combo, value) for all non-null results."""
    combos = list(itertools.product(*params))
    return [
        (c, r)
        for c, r in zip(combos, results)
        if r is not None and not (isinstance(r, float) and math.isnan(r))
    ]


def fmt_time(v):
    """Format a time value in seconds to a human-readable string."""
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


def fmt_mb(v):
    """Format MB value."""
    if v is None:
        return "n/a"
    if v >= 1024:
        return f"{v/1024:.1f} GB"
    return f"{v:.0f} MB"


def extract_summary(all_results):
    """Pull key numbers from results dict for use in the narrative."""
    s = {}

    # --- Bathymetry ---
    topo_key = "mom6_forge.bench_topo.TopoSetFromDataset.time_set_from_dataset"
    topo_mem_key = "mom6_forge.bench_topo.TopoSetFromDataset.track_rss_mb"
    if topo_key in all_results:
        results, params = all_results[topo_key]
        pairs = _valid_values(results, params)
        vals = [v for _, v in pairs]
        s["topo_min_s"] = min(vals)
        s["topo_max_s"] = max(vals)
        # param is domain_deg (integer degrees) in new results; try to parse as float
        # old results stored tuple-like strings '(100, 100)' — skip domain narrative for those
        try:
            by_domain = {float(short(c[0])): v for c, v in pairs}
            domain_vals = sorted(by_domain.keys())
            s["topo_domain_min_deg"] = domain_vals[0]
            s["topo_domain_max_deg"] = domain_vals[-1]
            s["topo_by_domain"] = by_domain
        except (ValueError, TypeError):
            pass  # old tuple-format params — domain narrative will be skipped
    if topo_mem_key in all_results:
        results, params = all_results[topo_mem_key]
        vals = [v for _, v in _valid_values(results, params)]
        s["topo_mem_mb"] = sum(vals) / len(vals)

    # --- xESMF weight generation ---
    xwt_key = "xesmf.bench_weights_generate.XESMFWeightsGenerate.time_generate_weights"
    xwt_mem_key = "xesmf.bench_weights_generate.XESMFWeightsGenerate.track_rss_mb"
    if xwt_key in all_results:
        results, params = all_results[xwt_key]
        pairs = _valid_values(results, params)
        # smallest: (300,300) src -> (150,150) dst, bilinear
        s["xwt_small_bilinear"] = _lookup(
            results, params, ("(300, 300)", "(150, 150)", "'bilinear'")
        )
        s["xwt_large_bilinear"] = _lookup(
            results, params, ("(1500, 700)", "(700, 350)", "'bilinear'")
        )
        s["xwt_small_conservative"] = _lookup(
            results, params, ("(300, 300)", "(150, 150)", "'conservative'")
        )
        s["xwt_large_conservative"] = _lookup(
            results, params, ("(1500, 700)", "(700, 350)", "'conservative'")
        )
    if xwt_mem_key in all_results:
        results, params = all_results[xwt_mem_key]
        vals = [v for _, v in _valid_values(results, params)]
        s["xwt_mem_min_mb"] = min(vals)
        s["xwt_mem_max_mb"] = max(vals)

    # --- xESMF locstream weight generation ---
    xloc_key = "xesmf.bench_weights_generate.XESMFWeightsGenerateLocstream.time_generate_weights"
    if xloc_key in all_results:
        results, params = all_results[xloc_key]
        vals = [v for _, v in _valid_values(results, params)]
        s["xloc_min_s"] = min(vals)
        s["xloc_max_s"] = max(vals)

    # --- xESMF regrid apply ---
    xapp_key = "xesmf.bench_regrid_apply.XESMFRegridApply.time_apply"
    if xapp_key in all_results:
        results, params = all_results[xapp_key]
        # 1 timestep, small grid, nearest_s2d (fastest)
        s["xapp_fast"] = _lookup(
            results, params, ("(300, 300)", "(150, 150)", "1", "'nearest_s2d'")
        )
        # 60 timesteps, large grid, bilinear (slowest)
        s["xapp_slow"] = _lookup(
            results, params, ("(1500, 700)", "(700, 350)", "60", "'bilinear'")
        )
        # speedup nearest vs bilinear (average across grid sizes, 60 timesteps)
        bilinear_60 = [
            _lookup(results, params, (src, dst, "60", "'bilinear'"))
            for src in ("(300, 300)", "(800, 600)", "(1500, 700)")
            for dst in ("(150, 150)", "(400, 300)", "(700, 350)")
        ]
        nn_60 = [
            _lookup(results, params, (src, dst, "60", "'nearest_s2d'"))
            for src in ("(300, 300)", "(800, 600)", "(1500, 700)")
            for dst in ("(150, 150)", "(400, 300)", "(700, 350)")
        ]
        ratios = [b / n for b, n in zip(bilinear_60, nn_60) if b and n]
        s["xapp_nn_speedup"] = sum(ratios) / len(ratios) if ratios else None

    # --- ESMF weight generation comparison ---
    ewt_key = "esmf.bench_weights_generate.ESMFWeightsGenerate.time_generate_weights"
    if ewt_key in all_results:
        results, params = all_results[ewt_key]
        s["ewt_small_bilinear"] = _lookup(
            results, params, ("(300, 300)", "(150, 150)", "'bilinear'")
        )
        s["ewt_large_bilinear"] = _lookup(
            results, params, ("(1500, 700)", "(700, 350)", "'bilinear'")
        )

    # --- ESMF apply (raw, no xarray overhead) ---
    eapp_key = "esmf.bench_regrid_apply.ESMFRegridApply.time_apply"
    if eapp_key in all_results:
        results, params = all_results[eapp_key]
        s["eapp_fast"] = _lookup(
            results, params, ("(300, 300)", "(150, 150)", "1", "'nearest_s2d'")
        )
        s["eapp_slow"] = _lookup(
            results, params, ("(1500, 700)", "(700, 350)", "60", "'bilinear'")
        )

    # --- Runoff mapping ---
    rof_nn_key = "mom6_forge.bench_runoff_mapping.RunoffMappingNearestNeighbour.time_gen_rof_maps_nn"
    rof_sm_key = "mom6_forge.bench_runoff_mapping.RunoffMappingSmoothed.time_gen_rof_maps_smoothed"
    if rof_nn_key in all_results:
        results, params = all_results[rof_nn_key]
        s["rof_nn_coarse"] = _lookup(results, params, ("'coarse'",))
        s["rof_nn_fine"] = _lookup(results, params, ("'fine'",))
    if rof_sm_key in all_results:
        results, params = all_results[rof_sm_key]
        s["rof_sm_coarse"] = _lookup(results, params, ("'coarse'",))
        s["rof_sm_fine"] = _lookup(results, params, ("'fine'",))

    # --- Module imports ---
    imp_key = "crocodash.bench_imports.CrocoDashImports.time_import"
    if imp_key in all_results:
        results, params = all_results[imp_key]
        s["import_crocodash"] = _lookup(results, params, ("'CrocoDash.case'",))
        s["import_grid"] = _lookup(results, params, ("'mom6_forge.grid'",))
        s["import_topo"] = _lookup(results, params, ("'mom6_forge.topo'",))
        s["import_vgrid"] = _lookup(results, params, ("'mom6_forge.vgrid'",))

    # --- Data access health ---
    health_key = "crocodash.bench_raw_data_access.DataAccessHealth.track_accessible"
    if health_key in all_results:
        results, params = all_results[health_key]
        pairs = _valid_values(results, params)
        s["health_ok"] = sum(1 for _, v in pairs if v == 1.0)
        s["health_total"] = len(pairs)

    return s


def build_narrative_html(all_results):
    """
    Build a human-readable summary section from the extracted benchmark stats.
    Returns an HTML string for a <section> element.
    """
    s = extract_summary(all_results)

    # Determine which suites have no results at all
    present_suites = {k.split(".")[0] for k in all_results}
    missing_benchmarks = []
    if "crocodash" not in present_suites or not any(
        "bench_obc" in k for k in all_results
    ):
        missing_benchmarks.append(
            "<b>OBC forcing pipeline</b> (<code>bench_obc.py</code>) — requires pre-staged "
            "GLORYS files and a CrocoDash case config. Set <code>obc_config_path</code> and "
            "<code>obc_step_days_dirs</code> in <code>data_config.json</code> to enable."
        )
    if not any("bench_runoff" in k for k in all_results):
        missing_benchmarks.append(
            "<b>Runoff mapping</b> (<code>bench_runoff_mapping.py</code>) — requires ESMF mesh "
            "NetCDF files. Set <code>mesh_pairs</code> in <code>data_config.json</code> to enable."
        )

    # Build paragraphs
    paras = []

    # Bathymetry
    if "topo_min_s" in s:
        mem_str = fmt_mb(s.get("topo_mem_mb"))
        by_domain = s.get("topo_by_domain", {})
        domain_min = s.get("topo_domain_min_deg")
        domain_max = s.get("topo_domain_max_deg")
        # Build a representative sentence if we have multiple domain sizes
        if by_domain and len(by_domain) > 1 and domain_min and domain_max:
            t_small = by_domain.get(domain_min)
            t_large = by_domain.get(domain_max)
            scaling_str = (
                f"A <b>{int(domain_min)}°×{int(domain_min)}°</b> domain takes "
                f"<b>{fmt_time(t_small)}</b>; "
                f"a <b>{int(domain_max)}°×{int(domain_max)}°</b> domain takes "
                f"<b>{fmt_time(t_large)}</b>."
                if t_small and t_large
                else f"Times range from <b>{fmt_time(s['topo_min_s'])}</b> to "
                f"<b>{fmt_time(s['topo_max_s'])}</b> across tested domain sizes."
            )
        else:
            scaling_str = (
                f"Time: <b>{fmt_time(s['topo_min_s'])}–{fmt_time(s['topo_max_s'])}</b>."
            )
        mem_note = (
            f" Memory usage averages <b>~{mem_str}</b>." if mem_str != "n/a" else ""
        )
        paras.append(f"""<h3>Bathymetry — <code>Topo.set_from_dataset()</code></h3>
<p>The cost of loading GEBCO bathymetry and regridding it onto a model grid scales with
<em>domain extent</em>, not destination resolution. Before regridding, the pipeline slices
GEBCO to the model bounding box — so a larger geographic region means more source data
to read and interpolate, regardless of how fine the destination grid is.
{scaling_str} All grids are generated at 0.1° resolution, so larger domains also produce
larger destination grids.{mem_note}</p>""")

    # xESMF / ESMF weight generation
    if "xwt_small_bilinear" in s:
        conservative_overhead = None
        if s.get("xwt_small_bilinear") and s.get("xwt_small_conservative"):
            conservative_overhead = (
                s["xwt_small_conservative"] / s["xwt_small_bilinear"]
            )
        conservative_str = (
            f" Conservative interpolation takes roughly {conservative_overhead:.1f}× "
            f"longer than bilinear at the same grid size."
            if conservative_overhead
            else ""
        )
        esmf_note = ""
        if "ewt_small_bilinear" in s and s.get("xwt_small_bilinear"):
            ratio = s["ewt_small_bilinear"] / s["xwt_small_bilinear"]
            esmf_note = (
                f" Raw ESMF weight generation is similar in cost ({ratio:.2f}× relative to xESMF "
                f"for the same grid pair), confirming that xESMF's overhead is negligible — "
                f"it is a thin Python wrapper around the same ESMF C library."
            )
        mem_range = ""
        if "xwt_mem_min_mb" in s:
            mem_range = (
                f" Weight files themselves occupy {fmt_mb(s['xwt_mem_min_mb'])}–"
                f"{fmt_mb(s['xwt_mem_max_mb'])} of RSS memory."
            )
        paras.append(
            f"""<h3>Regridding weights — <code>xe.Regridder()</code> / raw ESMF</h3>
<p>Computing interpolation weights (the one-time setup cost before any regridding can happen)
scales with grid size. For a <b>300×300 source → 150×150 destination</b> grid, bilinear weight
generation takes <b>{fmt_time(s['xwt_small_bilinear'])}</b>; scaling up to
<b>1500×700 → 700×350</b> takes <b>{fmt_time(s['xwt_large_bilinear'])}</b>.{conservative_str}{esmf_note}{mem_range}</p>"""
        )

    # Locstream (OBC-style)
    if "xloc_min_s" in s:
        paras.append(f"""<h3>OBC-style (locstream) weight generation</h3>
<p>When the destination is a boundary line of points rather than a full grid
(the pattern used for open-boundary conditions), weight generation is substantially
faster: <b>{fmt_time(s['xloc_min_s'])}–{fmt_time(s['xloc_max_s'])}</b> across the
tested source grid sizes. This is because the destination has far fewer points than
a full 2-D grid of similar extent.</p>""")

    # xESMF / ESMF apply comparison
    if "xapp_fast" in s:
        speedup_str = ""
        if s.get("xapp_nn_speedup"):
            speedup_str = (
                f" On average, <code>nearest_s2d</code> is "
                f"<b>{s['xapp_nn_speedup']:.1f}×</b> faster than bilinear during application."
            )
        esmf_apply_str = ""
        if s.get("eapp_fast") and s.get("eapp_slow"):
            xesmf_overhead_fast = (
                s["xapp_fast"] / s["eapp_fast"] if s["eapp_fast"] else None
            )
            xesmf_overhead_slow = (
                s["xapp_slow"] / s["eapp_slow"] if s["eapp_slow"] else None
            )
            if xesmf_overhead_fast and xesmf_overhead_slow:
                esmf_apply_str = (
                    f" Raw ESMF (no xarray) applies the same pre-computed weights considerably "
                    f"faster: <b>{fmt_time(s['eapp_fast'])}</b> and <b>{fmt_time(s['eapp_slow'])}</b> "
                    f"for the same two cases — roughly <b>{xesmf_overhead_fast:.0f}×</b> and "
                    f"<b>{xesmf_overhead_slow:.1f}×</b> faster respectively. The gap is largest for "
                    f"single timesteps, where xESMF's xarray Dataset → numpy conversion and index "
                    f"alignment dominate; it narrows for many timesteps on large grids where the "
                    f"actual interpolation work takes over. In practice xESMF is used because it "
                    f"handles multi-variable, dask-backed arrays transparently — the overhead is a "
                    f"deliberate trade-off for API convenience."
                )
        paras.append(
            f"""<h3>Applying pre-computed weights — <code>regridder(ds)</code></h3>
<p>Once weights are built, applying them to a data array is fast regardless of grid size.
Using xESMF, a single timestep on a small grid takes <b>{fmt_time(s['xapp_fast'])}</b>;
60 timesteps on the largest tested grid takes <b>{fmt_time(s['xapp_slow'])}</b>.
The cost is dominated by the number of destination points and time steps,
not the source grid size.{speedup_str}{esmf_apply_str}</p>"""
        )

    # Runoff mapping
    if "rof_nn_coarse" in s or "rof_sm_coarse" in s:
        nn_str = ""
        sm_str = ""
        ratio_str = ""
        if s.get("rof_nn_coarse") and s.get("rof_nn_fine"):
            nn_str = (
                f"Nearest-neighbour mapping takes <b>{fmt_time(s['rof_nn_coarse'])}</b> (coarse mesh) "
                f"and <b>{fmt_time(s['rof_nn_fine'])}</b> (fine mesh)."
            )
        if s.get("rof_sm_coarse") and s.get("rof_sm_fine"):
            sm_str = (
                f" Smoothed nearest-neighbour — which runs NN first then spreads point sources "
                f"across neighbouring ocean cells — takes <b>{fmt_time(s['rof_sm_coarse'])}</b> "
                f"and <b>{fmt_time(s['rof_sm_fine'])}</b> for the same mesh pairs."
            )
        if s.get("rof_nn_coarse") and s.get("rof_sm_coarse"):
            r = s["rof_sm_coarse"] / s["rof_nn_coarse"]
            ratio_str = f" The smoothing step roughly doubles the wall time ({r:.1f}×)."
        paras.append(f"""<h3>Runoff mapping — <code>gen_rof_maps()</code></h3>
<p><code>gen_rof_maps()</code> builds ESMF regridding weight files that map river runoff from
a land-model (ROF) mesh onto the ocean (OCN) model mesh. These weight files are computed once
and reused for every model run. The ROF source mesh is held constant (JRA55) across all pairs;
only the OCN destination grid varies — from coarse (1/10°) through fine (1/40°) to a larger
regional domain — so timing directly reflects how destination grid size drives cost.
{nn_str}{sm_str}{ratio_str}</p>""")

    # Imports
    if "import_crocodash" in s:
        paras.append(f"""<h3>Module import times</h3>
<p>Importing CrocoDash and mom6_forge is fast enough to be negligible in any workflow:
<code>CrocoDash.case</code> loads in <b>{fmt_time(s['import_crocodash'])}</b>,
<code>mom6_forge.topo</code> in <b>{fmt_time(s['import_topo'])}</b>,
and <code>mom6_forge.grid</code> / <code>mom6_forge.vgrid</code> in
<b>{fmt_time(s['import_grid'])}</b> / <b>{fmt_time(s['import_vgrid'])}</b>.</p>""")

    # Data health
    if "health_ok" in s:
        all_ok = s["health_ok"] == s["health_total"]
        status = "All" if all_ok else f"{s['health_ok']} of {s['health_total']}"
        color = "#1a7a3e" if all_ok else "#b85c00"
        paras.append(f"""<h3>Data source availability</h3>
<p><span style="color:{color};font-weight:600">{status} checked data sources are accessible.</span>
Each method is validated on every benchmark run; the table below shows pass/fail status and
how long each validation took.</p>""")

    # Missing benchmarks
    if missing_benchmarks:
        items = "".join(f"<li>{m}</li>" for m in missing_benchmarks)
        paras.append(f"""<h3>Not yet measured</h3>
<p>The following benchmark suites exist in the codebase but have no results yet because
they depend on data files that are not configured in <code>data_config.json</code>:</p>
<ul>{items}</ul>""")

    # xESMF/ESMF stability note
    paras.append("""<h3>A note on xESMF and ESMF benchmarks</h3>
<p>xESMF and ESMF are external libraries — they are not part of CrocoDash or mom6_forge and
their performance will <em>not</em> change from commit to commit on those repos.
These benchmarks serve as a stable reference: they tell you how fast the underlying regridding
engine is on this machine, independently of any CROC code changes.
If these numbers change significantly between runs, suspect a different library version,
different node type, or different CPU load — not a regression in CROC code.</p>""")

    inner = "\n".join(paras)
    return f"""
<section id="summary">
  <h2>Summary</h2>
  <div class="narrative">
{inner}
  </div>
</section>"""


_HEALTH_KEYS = {
    "accessible": "crocodash.bench_raw_data_access.DataAccessHealth.track_accessible",
    "timing": "crocodash.bench_raw_data_access.DataAccessHealth.time_validate",
    "link": "crocodash.bench_raw_data_access.DataAccessLinkCheck.track_link_ok",
}


def _parse_pm(param_str):
    """'('glorys', 'get_data')' → ('glorys', 'get_data')"""
    m = re.findall(r"'([^']+)'", param_str)
    return (m[0], m[1]) if len(m) >= 2 else (param_str, "")


def make_health_table(all_results):
    """
    HTML table: one row per (product, method).
    Columns: product/method | Working? (Yes/No) | Validation time.
    Returns an HTML string or None.
    """
    h_key = _HEALTH_KEYS["accessible"]
    t_key = _HEALTH_KEYS["timing"]
    if h_key not in all_results:
        return None

    h_results, h_params = all_results[h_key]
    h_combos = list(itertools.product(*h_params))

    time_lookup = {}
    if t_key in all_results:
        t_results, t_params = all_results[t_key]
        for combo, t in zip(itertools.product(*t_params), t_results):
            time_lookup[combo] = t

    # Link check is per-product — build lookup keyed by product name string
    link_lookup = {}
    l_key = _HEALTH_KEYS["link"]
    if l_key in all_results:
        l_results, l_params = all_results[l_key]
        for combo, lv in zip(itertools.product(*l_params), l_results):
            # combo[0] is the product name param string, e.g. "'glorys'"
            prod_name = combo[0].strip("'\"")
            link_lookup[prod_name] = lv

    rows = []
    for combo, h in zip(h_combos, h_results):
        product, method = _parse_pm(combo[0])
        label = f"{product} / {method.replace('_', ' ')}"
        ok = (h == 1.0) if h is not None else False
        t = time_lookup.get(combo)
        valid_t = (
            t if (t is not None and not (isinstance(t, float) and math.isnan(t))) else None
        )
        link_val = link_lookup.get(product)
        rows.append((label, ok, valid_t, link_val))

    if not rows:
        return None

    def _yn(val):
        if val is None:
            return '<span style="color:#999">—</span>'
        return (
            '<span style="color:#1a7a3e;font-weight:600">Yes</span>'
            if val == 1.0
            else '<span style="color:#b30000;font-weight:600">No</span>'
        )

    tr_rows = []
    for i, (label, ok, t, link_val) in enumerate(rows):
        bg = ' style="background:#f7f9fc"' if i % 2 == 0 else ""
        time_html = fmt_time(t) if t is not None else '<span style="color:#999">—</span>'
        tr_rows.append(
            f"<tr{bg}>"
            f"<td style='padding:0.3rem 0.5rem'>{label}</td>"
            f"<td style='text-align:center;padding:0.3rem 0.5rem'>{_yn(1.0 if ok else 0.0)}</td>"
            f"<td style='text-align:center;padding:0.3rem 0.5rem'>{_yn(link_val)}</td>"
            f"<td style='text-align:right;padding:0.3rem 0.5rem;font-variant-numeric:tabular-nums'>{time_html}</td>"
            f"</tr>"
        )

    return (
        '<table style="width:100%;border-collapse:collapse;font-size:0.88rem">'
        '<thead><tr style="border-bottom:2px solid #c8d6e5;color:#555;font-weight:600">'
        '<th style="text-align:left;padding:0.35rem 0.5rem">Product / Method</th>'
        '<th style="text-align:center;padding:0.35rem 0.5rem">Working?</th>'
        '<th style="text-align:center;padding:0.35rem 0.5rem">Link?</th>'
        '<th style="text-align:right;padding:0.35rem 0.5rem">Validation time</th>'
        f"</tr></thead><tbody>{''.join(tr_rows)}</tbody></table>"
    )


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

    all_values = [r for _, r in valid_pairs]
    finite = [
        v for v in all_values if v and not (isinstance(v, float) and math.isnan(v))
    ]
    use_log = len(finite) > 1 and max(finite) / min(finite) > 100

    def fmt_val(v):
        if v is None or (isinstance(v, float) and math.isnan(v)):
            return ""
        if unit == "s":
            if v >= 1:
                return f"{v:.2f}s"
            if v >= 1e-3:
                return f"{v*1e3:.1f}ms"
            if v >= 1e-6:
                return f"{v*1e6:.1f}μs"
            return f"{v*1e9:.1f}ns"
        if unit == "MB":
            return f"{v:.1f}MB"
        return f"{v:.3g}"

    if len(params) == 1:
        labels = [short(c[0]) for c, _ in valid_pairs]
        values = [r for _, r in valid_pairs]

        fig, ax = plt.subplots(figsize=(max(5, len(labels) * 0.9 + 1), 4))
        bars = ax.bar(range(len(labels)), values, color="#4c78a8", width=0.6)
        ax.bar_label(bars, labels=[fmt_val(v) for v in values], padding=3, fontsize=8)
        ax.set_xticks(range(len(labels)))
        ax.set_xticklabels(labels, rotation=25, ha="right", fontsize=9)
        if use_log:
            ax.set_yscale("log")
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
            bars = ax.bar(
                offsets,
                values,
                width=width,
                label=short(g),
                color=colors[i],
                alpha=0.88,
            )
            ax.bar_label(
                bars, labels=[fmt_val(v) for v in values], padding=2, fontsize=7
            )

        center = (n_g - 1) * width / 2
        x_labels = [" × ".join(short(v) for v in xc) for xc in x_combos]
        ax.set_xticks([j + center for j in range(n_x)])
        ax.set_xticklabels(x_labels, rotation=30, ha="right", fontsize=8)
        if use_log:
            ax.set_yscale("log")
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
    narrative = build_narrative_html(all_results)

    # Group by suite
    by_suite = {}
    for key, (results, params) in sorted(all_results.items()):
        suite = key.split(".")[0]
        by_suite.setdefault(suite, {})[key] = (results, params)

    # Build combined health table once; its keys are skipped in the generic loop.
    health_html = make_health_table(all_results)
    health_card = ""
    if health_html:
        health_card = f"""
        <div class="card" id="data-access-health">
          <h3>DataAccessHealth — all products</h3>
          {health_html}
        </div>"""

    sections = []
    for suite, benchmarks in sorted(by_suite.items()):
        suite_label = SUITE_LABELS.get(suite, suite)
        cards = []

        # Insert the combined health card in the crocodash section.
        if suite == "crocodash" and health_card:
            cards.append(health_card)

        for key, (results, params) in sorted(benchmarks.items()):
            # Health keys are handled by make_health_table above — skip individual charts.
            if key in _HEALTH_KEYS.values():
                continue
            b64 = make_chart(key, results, params)
            if b64 is None:
                continue
            name = bench_display_name(key)
            param_info = param_table_html(params)
            cards.append(f"""
        <div class="card">
          <h3>{name}</h3>
          <div class="params">{param_info}</div>
          <img src="data:image/png;base64,{b64}" alt="{name}">
        </div>""")

        if not cards:
            continue

        sections.append(f"""
    <section>
      <h2>{suite_label}</h2>
      <div class="grid">{"".join(cards)}
      </div>
    </section>""")

    chart_body = (
        "\n".join(sections) if sections else "<p>No benchmark results found.</p>"
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
  /* Narrative summary styles */
  #summary {{ background: #fff; border-bottom: 1px solid #dde4ee; }}
  .narrative {{ max-width: 820px; }}
  .narrative h3 {{ font-size: 1rem; color: #1a3a5c; margin: 1.4rem 0 0.35rem; }}
  .narrative h3:first-child {{ margin-top: 0; }}
  .narrative p {{ margin: 0 0 0.5rem; line-height: 1.65; font-size: 0.92rem; color: #333; }}
  .narrative ul {{ margin: 0.4rem 0 0.8rem 1.2rem; padding: 0; }}
  .narrative li {{ font-size: 0.92rem; line-height: 1.6; color: #333; margin-bottom: 0.3rem; }}
  .narrative code {{ background: #eef1f6; padding: 0.1em 0.35em;
                     border-radius: 3px; font-size: 0.85em; }}
  .divider {{ border: none; border-top: 2px solid #c8d6e5; margin: 0.5rem 0 0; }}
  #charts-heading {{ padding: 0.75rem 2rem 0; font-size: 1rem; color: #555; }}
</style>
</head>
<body>
<header>
  <h1>SeaSloth Benchmark Report</h1>
  <p>Performance snapshot — benchmarks run on Derecho/GLADE.
     <a href="asv_timeline.html" style="color:#9fc3e8">Regression timeline &rarr;</a>
     <span style="opacity:0.5;font-size:0.8rem">(needs 2+ commits to show data)</span></p>
</header>
{narrative}
<p id="charts-heading" style="color:#888;font-size:0.85rem">Detailed charts below &darr;</p>
{chart_body}
<footer>
  Generated by <code>scripts/generate_report.py</code> &mdash;
  <a href="https://github.com/CROCODILE-CESM/SeaSloth">SeaSloth</a>
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

    # Preserve ASV's index.html as asv_timeline.html before overwriting
    asv_index = OUTPUT_FILE.parent / "asv_timeline.html"
    if OUTPUT_FILE.exists():
        shutil.copy2(OUTPUT_FILE, asv_index)

    html = build_html(all_results)
    OUTPUT_FILE.write_text(html)
    print(f"Report written to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
