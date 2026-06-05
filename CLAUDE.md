# CLAUDE.md

This file provides guidance to Claude Code when working in this repository.

## Project Overview

**CrocoScope** is the performance benchmarking suite for the CROC ocean modeling ecosystem (CrocoDash, mom6_forge, regional-mom6). It uses [ASV (Airspeed Velocity)](https://asv.readthedocs.io/) to measure and track the performance of computationally expensive operations — xESMF/ESMF weight generation, bathymetry regridding, OBC forcing pipelines — across commits, and presents results in an interactive HTML dashboard.

GitHub org: https://github.com/CROCODILE-CESM

## What is being benchmarked

| Suite | File(s) | Status | What it measures |
|---|---|---|---|
| xESMF regridder creation | `xesmf/bench_regridder_creation.py` | Implemented | ESMF weight generation time + RSS across grid sizes/methods |
| xESMF regridder apply | `xesmf/bench_regridder_apply.py` | Implemented | Regridder application time across grid sizes/ntime/nvars |
| mom6_forge kdtree | `mom6_forge/bench_grid_kdtree.py` | Implemented | cKDTree build time + RSS; batch query time |
| mom6_forge grid metrics | `mom6_forge/bench_grid_metrics.py` | Implemented | `_compute_MOM6_grid_metrics()` across grid sizes |
| mom6_forge topo regrid | `mom6_forge/bench_topo_regrid.py` | Implemented | `regrid_dataset_via_xesmf()` (synthetic); `Topo.set_from_dataset()` (GEBCO) |
| mom6_forge topo tidy | `mom6_forge/bench_topo_tidy.py` | Implemented | `tidy_dataset()` binary_fill_holes across grid sizes |
| mom6_forge subsampling | `mom6_forge/bench_regrid_subsampling.py` | Implemented | `regrid_with_subsampling()` across dst sizes and sub-sample densities |
| GLORYS RDA throughput | `crocodash/bench_raw_data_access.py` | Implemented | MB/s from GLADE campaign storage |
| GLORYS Copernicus throughput | `crocodash/bench_raw_data_access.py` | Implemented | MB/s via Copernicus Marine API |
| CrocoDash OBC pipeline | `crocodash/bench_obc.py` | Stub | Full process_obc_conditions() — needs cached GLORYS |
| End-to-end CESM case | `e2e/bench_case_workflow.py` | Stub | Full case setup timing — HPC only |

## Framework: ASV

ASV discovers benchmarks by importing every `bench_*.py` file under `benchmarks/` and finding classes with methods starting with `time_`, `mem_`, `peakmem_`, or `track_`. Each method + parameter combo is a separate benchmark run in a fresh subprocess.

Key conventions:
- `setup(self, *params)` — runs before timing, excluded from measurement; put expensive construction here
- `time_*` — timed with `timeit`; ASV auto-selects number of reps
- `track_rss_mb` — custom `track_*` using psutil RSS; captures C/Fortran heap (ESMF) that `mem_*` and `peakmem_*` miss
- `teardown(self, *params)` — cleanup after timing (temp files, etc.)
- `NotImplementedError` in `setup()` marks a benchmark as `n/a` (data-dependent or HPC-only)

## Directory Structure

```
CrocoScope/
├── asv.conf.json                         # ASV config — environment_type, matrix, result paths
├── benchmarks/
│   ├── __init__.py                       # Sets ESMFMKFILE + adds mom6_forge/CrocoDash to sys.path
│   ├── data_config.json                  # Paths to GEBCO, GLORYS, and local package sources
│   ├── common/
│   │   ├── synthetic_data.py             # make_rect_grid(), make_curvilinear_grid(), etc.
│   │   └── config.py                     # get_path() helper to read data_config.json
│   ├── xesmf/                            # xESMF/ESMF weight generation and application
│   ├── mom6_forge/                       # mom6_forge Grid/Topo/mapping operations
│   ├── crocodash/                        # CrocoDash data access + OBC pipeline
│   └── e2e/                              # End-to-end CESM case timing (stub, HPC only)
├── results/                              # ASV result JSON — commit these to track history
├── scripts/
│   ├── run_fast.sh                       # mom6_forge grid/kdtree/tidy/subsampling (no xesmf)
│   ├── run_full.sh                       # All benchmarks including xesmf (Casper)
│   ├── publish.sh                        # Build .asv/html/ dashboard
│   └── pbs_submit.sh                     # PBS job for data-dependent benchmarks
├── docs/
│   ├── how_benchmarking_works.md         # ASV internals deep-dive
│   └── adding_benchmarks.md             # How to write a new benchmark
└── .github/workflows/benchmark.yml      # CI: only runs asv publish (not benchmarks)
```

## Running Benchmarks

**Always use `asv run HEAD` — never `asv run EXISTING` or `asv run --python /path`.**

```bash
# Fast mom6_forge benchmarks (no ESMF, safe on login node)
bash scripts/run_fast.sh

# Full run including xesmf (Casper interactive node)
bash scripts/run_full.sh

# Data-dependent benchmarks (GEBCO, GLORYS) — PBS job
qsub scripts/pbs_submit.sh

# Build dashboard from committed results
bash scripts/publish.sh
```

To run a single benchmark class:
```bash
/glade/work/manishrv/conda-envs/CrocoDash/bin/python -m asv run --bench "GridKDTreeBuild" --quick HEAD
```

After any run, commit `results/` so the dashboard history accumulates:
```bash
git add results/
git commit -m "add benchmark results: <description of what changed>"
git push
```

## Critical: environment_type, sys.path, and ESMFMKFILE

`asv.conf.json` uses `"environment_type": "conda"`. ASV builds a managed conda env in `env/` from the `matrix`. **Always use `HEAD` as the range spec.**

Two things that do NOT save results and must never be used:
- `asv run --python /path` — terminal quick-check only, results discarded
- `asv run EXISTING` — requires git version tags to resolve commit; fails without them

**mom6_forge and CrocoDash** are not conda packages. `benchmarks/__init__.py` adds them to `sys.path` by reading source paths from `benchmarks/data_config.json`. Edit that file if paths change.

**ESMFMKFILE** is set inside benchmark subprocesses by `benchmarks/__init__.py` (globs `env/*/lib/esmf.mk`). ASV doesn't source conda activation scripts, so without this the xesmf import crashes with a version mismatch error.

## What CrocoScope tracks

ASV tags results with CrocoScope's own commit hash — not CrocoDash or mom6_forge commits. To track the effect of a change in those packages: make the change, run benchmarks, commit the result JSON with a descriptive message. The dashboard X-axis is CrocoScope commits, but the useful signal is the commit message.

## Memory Benchmarks

CrocoScope uses `track_rss_mb` (not `mem_*`) for memory measurements because ESMF performs large C/Fortran heap allocations invisible to Python's `sys.getsizeof` and `tracemalloc`.

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
| `make_rect_grid(nlon, nlat)` | 1D lon/lat xr.Dataset with bounds | xESMF source; subsampling input |
| `make_curvilinear_grid(nlon, nlat)` | 2D lon/lat xr.Dataset with bounds | xESMF destination |
| `make_locstream_grid(n)` | 1D ncells xr.Dataset | OBC boundary (locstream_out=True) |
| `make_data_variable(grid, ntime, nvars)` | grid + data variables | Anything needing data to regrid |

For mom6_forge Grid benchmarks, use `Grid(lenx, leny, nx, ny)` directly — not `make_supergrid`.

## CI

The GitHub Actions workflow (`.github/workflows/benchmark.yml`) only runs `asv publish` — it never runs benchmarks. Benchmarks run locally on GLADE. Results are committed to `results/` in git. CI checks out the repo with full history (`fetch-depth: 0`) so ASV can resolve all result commit hashes, then deploys to GitHub Pages.

## Linting

Use black before committing:
```bash
black benchmarks/
```
