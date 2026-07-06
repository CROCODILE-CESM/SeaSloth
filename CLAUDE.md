# CLAUDE.md

This file provides guidance to Claude Code when working in this repository.

## Project Overview

**SeaSloth** is a one-time performance snapshot for parts of the CROC ocean modeling
ecosystem that don't change commit-to-commit: xESMF/ESMF regridding (external libraries),
the mom6_forge bathymetry pipeline, and the CrocoDash OBC regrid+merge pipeline. It uses
[pytest-benchmark](https://pytest-benchmark.readthedocs.io/) and renders two static HTML
pages of plain tables — no charts, no hand-written narrative.

Commit-by-commit performance tracking for CrocoDash/mom6_forge code lives in those repos'
own pytest-benchmark suites — not here. SeaSloth previously used ASV (airspeed velocity)
for commit tracking; that's gone.

GitHub org: https://github.com/CROCODILE-CESM

## What is being benchmarked

| Suite | File(s) | Data needed | What it measures |
|---|---|---|---|
| xESMF weight generation | `xesmf/test_weights_generate.py` | None (synthetic) | `xe.Regridder()` construction time + RSS |
| xESMF regrid application | `xesmf/test_regrid_apply.py` | None (synthetic) | `regridder(ds)` time across grid sizes, time depths, methods |
| ESMF weight generation | `esmf/test_weights_generate.py` | None (synthetic) | raw `esmpy.Regrid()` construction — same sizes as xESMF |
| ESMF regrid application | `esmf/test_regrid_apply.py` | None (synthetic) | raw `esmpy.Regrid()(src, dst)` time |
| Bathymetry pipeline | `mom6_forge/test_topo.py` | GEBCO (GLADE) | `Topo.set_from_dataset()` — GEBCO regrid + fill across domain sizes |
| OBC forcing pipeline | `crocodash/test_obc.py` | Cached GLORYS (GLADE) | REGRID + MERGE of `process_conditions()`, varying `step_days` |

Data-source health (link/`validate_function` checks) is a **separate**, daily-run concern —
see `scripts/check_data_access.py` below, not part of the pytest-benchmark suite.

## Framework: pytest-benchmark

Every benchmark is a normal pytest test using the `benchmark` fixture. `pytest.mark.parametrize`
replaces ASV's `params`/`param_names`; `@pytest.mark.skipif` replaces ASV's
`raise NotImplementedError` in `setup()` for data-dependent tests.

Key conventions:
- `benchmark(fn)` — times `fn`, calibrating reps automatically. Use for cheap, synthetic benchmarks.
- `benchmark.pedantic(fn, rounds=1, iterations=1, warmup_rounds=0)` — times `fn` exactly
  once. Use for expensive/data-dependent benchmarks (GEBCO regrid, GLORYS regrid+merge,
  network calls) where repeating the call for statistical calibration would be wasteful or slow.
- `benchmark.extra_info["rss_mb"] = ...` — memory tracking, since pytest-benchmark has no
  built-in memory measurement. See `benchmarks/common/memtrack.py`.
- `pytest.mark.light` / `pytest.mark.heavy` — the smallest parameter combination in a
  synthetic (xESMF/ESMF) sweep is tagged `light` for a fast smoke test; everything else is
  `heavy`. `test_topo.py` and `test_obc.py` are always `heavy` — even their smallest size
  needs real GEBCO/GLORYS data and takes meaningful time. Run just the light ones with
  `pytest -m light`.

## Directory Structure

```
SeaSloth/
├── pyproject.toml                        # deps + light/heavy marker registration
├── benchmarks/
│   ├── data_config.json                  # Paths to GEBCO, GLORYS, OBC config
│   ├── link_config.json                  # Product -> documentation URL, used by check_data_access.py
│   ├── common/
│   │   ├── synthetic_data.py             # make_rect_grid(), make_curvilinear_grid(), etc.
│   │   ├── config.py                     # get_path() helper to read data_config.json
│   │   ├── memtrack.py                   # measure_rss(fn, *a, **kw) -> (result, rss_mb)
│   │   └── marks.py                      # light_or_heavy(is_light) helper
│   ├── xesmf/                            # xESMF weight generation and application
│   ├── esmf/                             # Raw esmpy weight generation and application
│   ├── mom6_forge/                       # Topo.set_from_dataset()
│   └── crocodash/                        # OBC regrid+merge pipeline
├── results/
│   ├── latest.json                       # perf-benchmark snapshot (pytest-benchmark JSON), manual runs
│   └── health.json                       # data-access health snapshot, overwritten daily
├── scripts/
│   ├── run_benchmarks.sh                 # pytest wrapper -> results/latest.json
│   ├── generate_report.py                # results/latest.json -> report/index.html (tables)
│   ├── check_data_access.py              # link + validate_function checks -> results/health.json
│   ├── generate_health_report.py         # results/health.json -> report/health.html
│   ├── pbs_submit.sh                     # PBS job for the full perf suite on Derecho/Casper
│   └── pbs_data_health.sh                # self-resubmitting daily PBS job for health checks
├── docs/
│   ├── how_benchmarking_works.md
│   └── adding_benchmarks.md
└── .github/workflows/publish.yml         # manual dispatch + daily schedule: rebuild both pages, deploy Pages
```

## Running Benchmarks

```bash
conda activate CrocoDash

bash scripts/run_benchmarks.sh                # all perf benchmarks -> results/latest.json
bash scripts/run_benchmarks.sh -m light       # fast smoke test (synthetic suites only)
bash scripts/run_benchmarks.sh -k xesmf       # one suite

python scripts/generate_report.py             # -> report/index.html

# On Derecho — PBS job for the full suite (needs GEBCO/GLORYS data)
qsub scripts/pbs_submit.sh
```

Data access health runs separately, daily:

```bash
python scripts/check_data_access.py           # -> results/health.json
python scripts/generate_health_report.py      # -> report/health.html

# On GLADE — self-resubmitting daily job
qsub scripts/pbs_data_health.sh
```

## data_config.json

Keys that need to be set before HPC-dependent benchmarks will run:

| Key | Used by | Description |
|---|---|---|
| `gebco_path` | `test_topo.py` | Path to GEBCO_2024.nc |
| `obc_config_path` | `test_obc.py` | Path to a CrocoDash case config YAML |
| `obc_step_days_dirs` | `test_obc.py` | Dict mapping step_days → pre-staged raw GLORYS folder |

Tests using these paths skip via `pytest.mark.skipif`/`pytest.skip()` when the path is unset
or missing.

## Memory Benchmarks

Use `benchmarks/common/memtrack.py`'s `measure_rss(fn, *args, **kwargs)` — not ASV's
`track_rss_mb` convention. It returns `(result, rss_delta_mb)`; stash the delta into
`benchmark.extra_info["rss_mb"]`. This exists because ESMF performs large C/Fortran heap
allocations invisible to Python's `sys.getsizeof`/`tracemalloc`.

## Synthetic Data

Use helpers from `benchmarks/common/synthetic_data.py` — do not create grids inline.

| Function | Returns | Use for |
|---|---|---|
| `make_rect_grid(nlon, nlat)` | 1D lon/lat xr.Dataset with bounds | xESMF source |
| `make_curvilinear_grid(nlon, nlat)` | 2D lon/lat xr.Dataset with bounds | xESMF destination |
| `make_locstream_grid(n)` | 1D ncells xr.Dataset | OBC boundary (locstream_out=True) |
| `make_data_variable(grid, ntime, nvars)` | grid + data variables | Anything needing data to regrid |

For ESMF direct benchmarks use `_make_esmpy_grid(nlon, nlat)` defined inline in the
benchmark file — not the xarray helpers.

## Report generators

Both are plain stdlib (`json` + f-strings) — no matplotlib, no numpy, no image generation.
`scripts/generate_report.py` groups `results/latest.json`'s benchmarks by suite (parsed from
`fullname`) then by test function, rendering one table per function (params, mean, min, max,
rss). `scripts/generate_health_report.py` renders `results/health.json`'s `link_checks`/
`validate_checks` lists as two small tables. Neither computes cross-benchmark ratios or
writes prose — if you're tempted to add narrative back in, don't; that's the complexity this
rewrite removed.

## CI

`.github/workflows/publish.yml` triggers on `workflow_dispatch` and a daily `schedule`. It
never runs the actual benchmarks or health checks (GitHub's runners can't — no CrocoDash,
no GEBCO/GLORYS, no ESMF) — it only regenerates both report pages from whatever is currently
committed under `results/` and deploys to GitHub Pages.

## Linting

Use black before committing:
```bash
black benchmarks/ scripts/
```
