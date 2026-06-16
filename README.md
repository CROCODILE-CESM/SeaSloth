# CrocoScope

Performance benchmarking suite for the CROC ocean modeling ecosystem (CrocoDash, mom6_forge, regional-mom6, xESMF/ESMF regridding).

## What's Benchmarked

| Suite | Env | Speed | What it measures |
|---|---|---|---|
| `benchmarks/xesmf/` | CrocoDash | Slow | xESMF regridder creation + application at various grid sizes and methods |
| `benchmarks/mom6_forge/` | mom6_forge | Slow | Grid metrics, KDTree, bathymetry regridding |
| `benchmarks/crocodash/` | CrocoDash | Slow (HPC) | OBC forcing pipeline (process_obc_conditions) |
| `benchmarks/raw_data_access` | CrocoDash | Very slow (HPC) | All the data access methods |
| `benchmarks/CrocoDash Case Initialization` | CrocoDash | Slow (HPC) | The Case Init time across commits |

## Setup

CrocoScope uses `environment_type: "existing"` in `asv.conf.json`, meaning ASV uses your
existing conda environments directly rather than creating its own. You must pass your Python
binary explicitly via `--python` when running benchmarks — the scripts handle this.

**Prerequisites:**
1. The `CrocoDash` and `mom6_forge` conda environments installed (see the main CROC repo)
2. `asv` installed into whichever env you invoke the scripts from:
   ```bash
   pip install asv   # run inside CrocoDash or mom6_forge env
   ```
3. Edit the `PYTHON_*` variables at the top of each script in `scripts/` to point to your
   conda env Python binaries:
   ```bash
   # Find your paths:
   conda run -n CrocoDash which python
   conda run -n mom6_forge which python
   ```

## Quick Start

```bash
# Run fast benchmarks (safe for login nodes and CI — no HPC data required)
bash scripts/run_fast.sh

# Build and view the dashboard
bash scripts/publish.sh
# Open .asv/html/index.html in a browser or Jupyter file browser
```

## HPC (Casper/Derecho)

```bash
# Edit scripts/pbs_submit.sh: set -A to your project allocation code
qsub scripts/pbs_submit.sh
```

Slow benchmarks (OBC pipeline, topo regridding) raise `NotImplementedError` when their
required data files are absent, so they are skipped gracefully on login nodes and in CI.

## Running a Specific Suite

```bash
PYTHON=/path/to/your/conda/env/bin/python

# xESMF benchmarks, quick mode (one rep per param combo)
"$PYTHON" -m asv run --python "$PYTHON" --bench "xesmf" --quick

# Full timing for a single class
"$PYTHON" -m asv run --python "$PYTHON" --bench "RegridderCreation"
```

## Dashboard

```bash
bash scripts/publish.sh     # builds HTML from results/
# open .asv/html/index.html
```

## Dashboard and Results

The live dashboard is published to GitHub Pages on every push to `main`.

All benchmarks run locally on GLADE (login node or Casper interactive/PBS). CI only
publishes — it never runs benchmarks. The flow:

1. Run benchmarks locally (see scripts below)
2. Commit the results and push:
   ```bash
   git add results/
   git commit -m "add benchmark results: <brief description>"
   git push
   ```
3. CI picks up the committed results and rebuilds the dashboard automatically

> **First-time setup:** in the GitHub repo go to **Settings → Pages → Source** and
> set it to **GitHub Actions**. Only needs to be done once.

## Documentation

- [How benchmarking works](docs/how_benchmarking_works.md) — timing model, subprocess isolation, params, memory benchmarks, results storage
- [Adding new benchmarks](docs/adding_benchmarks.md) — benchmark class anatomy, CI/HPC split, synthetic data helpers
