# CLAUDE.md

This file provides guidance to Claude Code when working in this repository.

## Project Overview

**SeaSloth** is the performance benchmarking suite for the CROC ocean modeling ecosystem (CrocoDash, mom6_forge). It uses [ASV (Airspeed Velocity)](https://asv.readthedocs.io/) to measure computationally expensive operations — xESMF/ESMF weight generation, bathymetry pipelines, OBC forcing — and presents results in an interactive HTML dashboard.

GitHub org: https://github.com/CROCODILE-CESM

## What is being benchmarked

| Suite | File(s) | Data needed | What it measures |
|---|---|---|---|
| xESMF weight generation | `xesmf/bench_weights_generate.py` | None (synthetic) | `xe.Regridder()` construction time + RSS, grid→grid and grid→locstream, up to ~1 M source pts |
| xESMF regrid application | `xesmf/bench_regrid_apply.py` | None (synthetic) | `regridder(ds)` time across grid sizes, time depths, methods |
| ESMF weight generation | `esmf/bench_weights_generate.py` | None (synthetic) | `esmpy.Regrid()` construction — raw ESMF, same sizes as xESMF suite |
| ESMF regrid application | `esmf/bench_regrid_apply.py` | None (synthetic) | `esmpy.Regrid()(src, dst)` time per ntime steps — raw ESMF |
| OBC forcing pipeline | `crocodash/bench_obc.py` | Cached GLORYS (GLADE) | REGRID + MERGE of `process_conditions()`, no GET; varies step_days |
| Runoff mapping | `mom6_forge/bench_runoff_mapping.py` | ESMF mesh files (GLADE) | `gen_rof_maps()` — NN and smoothed NN mapping between ROF and OCN meshes |
| Raw data access health | `crocodash/bench_raw_data_access.py` | Credentials / GLADE | Connectivity check for GLORYS, GEBCO, GLOFAS, MOM6 output; returns 1/0 |
| Bathymetry pipeline | `mom6_forge/bench_topo.py` | GEBCO (GLADE) | `Topo.set_from_dataset()` — GEBCO regrid + fill across grid sizes |

## Framework: ASV

ASV discovers benchmarks by importing every `bench_*.py` file under `benchmarks/` and finding classes with methods starting with `time_`, `mem_`, `peakmem_`, or `track_`. Each method + parameter combo is a separate benchmark run in a fresh subprocess.

Key conventions:
- `setup(self, *params)` — runs before timing, excluded from measurement; put expensive construction here
- `time_*` — timed with `timeit`; ASV auto-selects number of reps
- `track_rss_mb` — custom `track_*` using psutil RSS; captures C/Fortran heap (ESMF) that `mem_*` and `peakmem_*` miss
- `teardown(self, *params)` — cleanup after timing (temp files, esmpy .destroy() calls)
- `NotImplementedError` in `setup()` marks a benchmark as `n/a` (data-dependent or HPC-only)

## Directory Structure

```
SeaSloth/
├── asv.conf.json                         # ASV config — environment_type, matrix, result paths
├── benchmarks/
│   ├── __init__.py                       # Sets ESMFMKFILE + adds mom6_forge/CrocoDash to sys.path
│   ├── data_config.json                  # Paths to GEBCO, GLORYS, mesh files, OBC config
│   ├── common/
│   │   ├── synthetic_data.py             # make_rect_grid(), make_curvilinear_grid(), etc.
│   │   └── config.py                     # get_path() helper to read data_config.json
│   ├── xesmf/                            # xESMF weight generation and application
│   ├── esmf/                             # Raw esmpy weight generation and application
│   ├── mom6_forge/                       # Topo.set_from_dataset() + gen_rof_maps()
│   ├── crocodash/                        # OBC pipeline + raw data health checks
│   └── e2e/                              # End-to-end CESM case timing (stub, HPC only)
├── results/                              # ASV result JSON — commit these to track history
├── scripts/
│   ├── publish.sh                        # Build .asv/html/ dashboard + report
│   └── pbs_submit.sh                     # PBS job for data-dependent benchmarks on Derecho
├── docs/
│   ├── how_benchmarking_works.md
│   └── adding_benchmarks.md
└── .github/workflows/benchmark.yml      # CI: asv publish + generate_report.py only
```

## Running Benchmarks

**Always use `asv run HEAD` — never `asv run EXISTING` or `asv run --python /path`.**

```bash
conda activate CrocoDash
python -m asv run

# Single class or suite
python -m asv run --bench "XESMFWeightsGenerate"
python -m asv run --bench "bench_raw_data_access"

# On Derecho — PBS job
qsub scripts/pbs_submit.sh

# Build dashboard from committed results
bash scripts/publish.sh
```

After any run, commit `results/` so the dashboard history accumulates:
```bash
git add results/
git commit -m "bench: <description>"
git push
```

## data_config.json

Keys that need to be set before HPC-dependent benchmarks will run:

| Key | Used by | Description |
|---|---|---|
| `gebco_path` | `bench_topo.py` | Path to GEBCO_2024.nc |
| `glorys_rda_path` | `bench_raw_data_access.py` | GLADE campaign storage root |
| `mesh_pairs` | `bench_runoff_mapping.py` | List of `{label, rof_mesh, ocn_mesh, rmax, fold}` dicts |
| `obc_config_path` | `bench_obc.py` | Path to a CrocoDash case config YAML |
| `obc_step_days_dirs` | `bench_obc.py` | Dict mapping step_days → pre-staged raw GLORYS folder |

## Critical: environment_type, sys.path, and ESMFMKFILE

`asv.conf.json` uses `"environment_type": "existing"`. ASV uses the currently active Python interpreter — no env building, no matrix. **Never specify a commit range** — with `existing` env, ASV benchmarks the current working tree and tags results with the current git HEAD automatically.

**mom6_forge and CrocoDash** must be installed in the `CrocoDash` conda environment (via `pip install -e .` or similar). They are imported directly — no `sys.path` manipulation.

**ESMFMKFILE** is set by conda's `activate.d` scripts when `conda activate CrocoDash` runs, and is inherited by ASV's benchmark subprocesses. No manual setup needed.

**esmpy teardown**: ESMF direct benchmarks must call `.destroy()` on esmpy Grid/Field/Regrid objects in `teardown()` to prevent ESMF internal state from leaking between benchmark subprocesses.

## Memory Benchmarks

SeaSloth uses `track_rss_mb` (not `mem_*`) for memory measurements because ESMF performs large C/Fortran heap allocations invisible to Python's `sys.getsizeof` and `tracemalloc`.

```python
def track_rss_mb(self, ...):
    import os, psutil
    proc = psutil.Process(os.getpid())
    before = proc.memory_info().rss
    # ... call being measured ...
    return (proc.memory_info().rss - before) / 1024**2

track_rss_mb.unit = "MB"
```

## Synthetic Data

Use helpers from `benchmarks/common/synthetic_data.py` — do not create grids inline.

| Function | Returns | Use for |
|---|---|---|
| `make_rect_grid(nlon, nlat)` | 1D lon/lat xr.Dataset with bounds | xESMF source |
| `make_curvilinear_grid(nlon, nlat)` | 2D lon/lat xr.Dataset with bounds | xESMF destination |
| `make_locstream_grid(n)` | 1D ncells xr.Dataset | OBC boundary (locstream_out=True) |
| `make_data_variable(grid, ntime, nvars)` | grid + data variables | Anything needing data to regrid |

For ESMF direct benchmarks use `_make_esmpy_grid(nlon, nlat)` defined inline in the benchmark file — not the xarray helpers.

## CI

The GitHub Actions workflow (`.github/workflows/benchmark.yml`) only runs `asv publish` and `generate_report.py` — it never runs benchmarks. Benchmarks run locally on GLADE. Results are committed to `results/` in git. CI checks out the repo with full history (`fetch-depth: 0`) so ASV can resolve all result commit hashes, then deploys to GitHub Pages.

## Dashboard

Two HTML outputs in `.asv/html/`:
- `index.html` — ASV commit-timeline view (good for spotting regressions)
- `report.html` — snapshot bar charts per benchmark class (good for parameter sweeps)

## Linting

Use black before committing:
```bash
black benchmarks/
```
