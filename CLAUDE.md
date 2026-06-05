# CLAUDE.md

This file provides guidance to Claude Code when working in this repository.

## Project Overview

**CrocoScope** is the performance benchmarking suite for the CROC ocean modeling ecosystem (CrocoDash, mom6_forge, regional-mom6). It uses [ASV (Airspeed Velocity)](https://asv.readthedocs.io/) to measure and track the performance of computationally expensive operations — xESMF/ESMF weight generation, bathymetry regridding, OBC forcing pipelines — across commits, and presents results in an interactive HTML dashboard.

GitHub org: https://github.com/CROCODILE-CESM

## Framework: ASV

ASV discovers benchmarks by importing every `bench_*.py` file under `benchmarks/` and finding classes with methods starting with `time_`, `mem_`, `peakmem_`, or `track_`. Each method + parameter combo is a separate benchmark run in a fresh subprocess.

Key conventions:
- `setup(self, *params)` — runs before timing, excluded from measurement; put expensive construction here
- `time_*` — timed with `timeit`; ASV auto-selects number of reps
- `track_rss_mb` — custom `track_*` using psutil RSS; captures C/Fortran heap (ESMF) that `mem_*` and `peakmem_*` miss
- `teardown(self, *params)` — cleanup after timing (temp files, etc.)
- `NotImplementedError` in `setup()` marks a benchmark as `n/a` (HPC-only stubs)

## Directory Structure

```
CrocoScope/
├── asv.conf.json                     # ASV config — environment_type, matrix, result paths
├── benchmarks/
│   ├── common/synthetic_data.py      # make_rect_grid(), make_curvilinear_grid(), make_locstream_grid(), make_data_variable(), make_supergrid()
│   ├── xesmf/                        # xESMF/ESMF weight generation and application
│   │   ├── bench_regridder_creation.py
│   │   └── bench_regridder_apply.py
│   ├── mom6_forge/                   # mom6_forge Grid/Topo operations (stubs)
│   ├── crocodash/                    # CrocoDash OBC pipeline (stubs, HPC only)
│   └── e2e/                          # End-to-end CESM case timing (stubs, HPC only)
├── results/                          # ASV result JSON — commit these to track history
├── scripts/
│   ├── run_fast.sh                   # Quick xesmf benchmarks on login node
│   ├── run_full.sh                   # Full benchmark run (Casper interactive)
│   ├── publish.sh                    # Build .asv/html/ dashboard
│   └── pbs_submit.sh                 # PBS job for HPC-only benchmarks
├── docs/
│   ├── how_benchmarking_works.md     # ASV internals deep-dive
│   └── adding_benchmarks.md          # How to write a new benchmark
└── .github/workflows/benchmark.yml  # CI: only runs asv publish (not benchmarks)
```

## Running Benchmarks

**Always use the scripts or `asv run HEAD` — never `asv run --python /path`.**

```bash
# Quick sanity check (xesmf suite, one rep per param)
bash scripts/run_fast.sh

# Full run (all non-HPC benchmarks)
bash scripts/run_full.sh

# Build dashboard from committed results
bash scripts/publish.sh

# HPC benchmarks (requires GLORYS/GEBCO data)
qsub scripts/pbs_submit.sh
```

To run a single benchmark class:
```bash
/glade/work/manishrv/conda-envs/CrocoDash/bin/python -m asv run --bench "RegridderCreation" --quick HEAD
```

After any run, commit `results/` so the dashboard history accumulates:
```bash
git add results/
git commit -m "add benchmark results: <description>"
```

## Critical: environment_type and how to run

`asv.conf.json` uses `"environment_type": "conda"`. ASV builds a managed conda env in `env/` using conda-forge packages listed in `matrix`. **Always use `HEAD` as the range spec:**

```bash
asv run HEAD
asv run --bench "RegridderCreation" --quick HEAD
```

Two things that do NOT save results and must never be used:
- `asv run --python /path` — terminal quick-check only, results discarded
- `asv run EXISTING` — requires git version tags to resolve commit; fails without them

`ESMFMKFILE` is exported by the scripts before running — ASV's conda env has an `esmf.mk` but doesn't source conda activation scripts, so the env var is never set otherwise. The scripts find it dynamically via `find env/ -name esmf.mk`.

## Memory Benchmarks

CrocoScope uses `track_rss_mb` (not `mem_*`) for memory measurements because ESMF performs large C/Fortran heap allocations invisible to Python's `sys.getsizeof` and `tracemalloc`.

```python
def track_rss_mb(self, ...):
    import os, psutil
    proc = psutil.Process(os.getpid())
    before = proc.memory_info().rss
    # ... call being measured ...
    return (proc.memory_info().rss - before) / 1024 ** 2

track_rss_mb.unit = "MB"
```

If you add `mem_*` methods that return `None`, ASV will report 0 — always return the object.

## Synthetic Data

Use helpers from `benchmarks/common/synthetic_data.py` — do not create grids inline in benchmark files.

| Function | Returns | Use for |
|---|---|---|
| `make_rect_grid(nlon, nlat)` | 1D lon/lat xr.Dataset with bounds | xESMF source grids |
| `make_curvilinear_grid(nlon, nlat)` | 2D lon/lat xr.Dataset with bounds | xESMF destination grids |
| `make_locstream_grid(n)` | 1D ncells xr.Dataset | OBC boundary (locstream_out=True) |
| `make_data_variable(grid, ntime, nvars)` | grid + data variables | Anything needing data to regrid |
| `make_supergrid(nx, ny)` | MOM6 supergrid layout | mom6_forge Grid benchmarks |

Both `make_rect_grid` and `make_curvilinear_grid` include `lon_b`/`lat_b` cell-edge bounds and CF `units` attributes — required for xESMF `conservative` regridding (accessed via `cf_xarray` internally).

## CI

The GitHub Actions workflow (`.github/workflows/benchmark.yml`) only runs `asv publish` — it never runs benchmarks. Benchmarks run locally on GLADE (login node or Casper). Results are committed to `results/` in git. CI checks out the repo (with committed results), builds the dashboard, and deploys to GitHub Pages.

This means: if no results are committed, the dashboard is empty. Always commit results after a run.

## HPC-only Benchmarks

Benchmarks in `benchmarks/mom6_forge/` (topo, subsampling) and `benchmarks/crocodash/` require GEBCO or GLORYS data on GLADE scratch. Their `setup()` raises `NotImplementedError` so they appear as `n/a` in the dashboard rather than failing. Run them via `scripts/pbs_submit.sh` from a Casper PBS job.

## Conda Environment

ASV creates and manages its own conda env in `env/` using conda-forge packages. First run takes ~5 minutes; subsequent runs reuse the cached env.

The CrocoDash env (`/glade/work/manishrv/conda-envs/CrocoDash/bin/python`) is used only to invoke `asv` itself — benchmarks run inside the ASV-managed env. The scripts export `ESMFMKFILE` pointing to that env's `esmf.mk` so xesmf can import successfully in benchmark subprocesses.

## Linting

Use black before committing:
```bash
black benchmarks/
```
