# SeaSloth

A one-time performance snapshot for parts of the CROC ocean modeling ecosystem that don't
change commit-to-commit: xESMF/ESMF regridding (external libraries), the mom6_forge
bathymetry pipeline, and the CrocoDash OBC regrid+merge pipeline. Commit-by-commit
performance tracking for CrocoDash/mom6_forge code itself lives in those repos' own
pytest-benchmark suites, not here.

Two static pages, no charts, no narrative — just tables of what pytest-benchmark measured.

## What's benchmarked

| Suite | File(s) | Data needed | What it measures |
|---|---|---|---|
| xESMF weight generation | `xesmf/test_weights_generate.py` | None (synthetic) | `xe.Regridder()` construction time + RSS, grid→grid and grid→locstream |
| xESMF regrid application | `xesmf/test_regrid_apply.py` | None (synthetic) | `regridder(ds)` time across grid sizes, time depths, methods |
| ESMF weight generation | `esmf/test_weights_generate.py` | None (synthetic) | `esmpy.Regrid()` construction — raw ESMF, same sizes as xESMF suite |
| ESMF regrid application | `esmf/test_regrid_apply.py` | None (synthetic) | `esmpy.Regrid()(src, dst)` time — raw ESMF |
| Bathymetry pipeline | `mom6_forge/test_topo.py` | GEBCO (GLADE) | `Topo.set_from_dataset()` — GEBCO regrid + fill across domain sizes |
| OBC forcing pipeline | `crocodash/test_obc.py` | Cached GLORYS (GLADE) | REGRID + MERGE phases of `process_conditions()`, varying `step_days` |

The xESMF/ESMF suites are pure-synthetic and marked `light`/`heavy` — the smallest
grid-size combination in each sweep is `light` (a fast smoke test), everything else is
`heavy`. `test_topo.py` and `test_obc.py` are always `heavy` — they need real GEBCO/GLORYS
data and take meaningful time even at their smallest parameter value.

Data-source health (are GLORYS/GEBCO/GLOFAS/etc. reachable?) is a separate concern —
see [Data access health](#data-access-health) below.

## Running the perf benchmarks

```bash
conda activate CrocoDash
bash scripts/configure.sh          # sanity-check the environment

bash scripts/run_benchmarks.sh                 # everything
bash scripts/run_benchmarks.sh -m light        # fast smoke test (synthetic suites only)
bash scripts/run_benchmarks.sh -k xesmf        # one suite
```

This writes `results/latest.json`. On Derecho, `qsub scripts/pbs_submit.sh` runs the full
suite (including the GEBCO/GLORYS-dependent ones) as a PBS job.

Build the report page:

```bash
python scripts/generate_report.py
open report/index.html
```

## Data access health

Whether GLORYS/GEBCO/GLOFAS/etc. are reachable and CrocoDash's access methods still work
is checked **daily**, independent of the perf benchmarks above:

```bash
conda activate CrocoDash
python scripts/check_data_access.py     # writes results/health.json
python scripts/generate_health_report.py
open report/health.html
```

On GLADE, `qsub scripts/pbs_data_health.sh` starts a self-resubmitting daily job that runs
the check, overwrites `results/health.json`, and pushes it.

## HPC data-dependent benchmarks

Fill in paths in `benchmarks/data_config.json` to enable the tests that need real data:

| Key | Benchmark | What to put |
|---|---|---|
| `gebco_path` | `test_topo.py` | Path to `GEBCO_2024.nc` |
| `obc_config_path` | `test_obc.py` | Path to a CrocoDash case config |
| `obc_step_days_dirs` | `test_obc.py` | Three pre-staged raw GLORYS folders (one per `step_days`) |

Tests skip gracefully (`pytest.mark.skipif` / `pytest.skip`) when the required data isn't
configured.

## CI

`.github/workflows/publish.yml` runs on manual dispatch and a daily schedule. It never runs
the actual benchmarks or health checks — it just regenerates both report pages from
whatever is currently committed under `results/` and deploys them to GitHub Pages.
> **First-time GitHub Pages setup:** Settings → Pages → Source → GitHub Actions.

## Documentation

- [How benchmarking works](docs/how_benchmarking_works.md)
- [Adding new benchmarks](docs/adding_benchmarks.md)
