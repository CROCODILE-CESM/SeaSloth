# CrocoScope

Performance benchmarking suite for the CROC ocean modeling ecosystem (CrocoDash, mom6_forge, regional-mom6, xESMF/ESMF regridding).

## What's Benchmarked

| Suite | Env | Speed | What it measures |
|---|---|---|---|
| `benchmarks/xesmf/` | CrocoDash | Fast (CI/local) | xESMF regridder creation + application at various grid sizes and methods |
| `benchmarks/mom6_forge/` | mom6_forge | Fast–Medium | Grid metrics, KDTree, bathymetry regridding, tidy_dataset |
| `benchmarks/crocodash/` | CrocoDash | Slow (HPC) | OBC forcing pipeline (process_obc_conditions) |
| `benchmarks/e2e/` | CrocoDash | Very slow (HPC) | End-to-end case workflow timing |

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

## Adding New Benchmarks

See [docs/adding_benchmarks.md](docs/adding_benchmarks.md).
