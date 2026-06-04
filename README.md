# CrocoScope

Performance benchmarking suite for the CROC ocean modeling ecosystem (CrocoDash, mom6_forge, regional-mom6, xESMF/ESMF regridding).

## What's Benchmarked

| Suite | Env | Speed | What it measures |
|---|---|---|---|
| `benchmarks/xesmf/` | CrocoDash | Fast (CI/local) | xESMF regridder creation + application at various grid sizes and methods |
| `benchmarks/mom6_forge/` | mom6_forge | Fast–Medium | Grid metrics, KDTree, bathymetry regridding, tidy_dataset |
| `benchmarks/crocodash/` | CrocoDash | Slow (HPC) | OBC forcing pipeline (process_obc_conditions) |
| `benchmarks/e2e/` | CrocoDash | Very slow (HPC) | End-to-end case workflow timing |

## Quick Start

```bash
# Install asv (one-time, into whichever env you're using)
conda activate CrocoDash
pip install asv

# Run fast benchmarks only (safe for login node / CI)
bash scripts/run_fast.sh

# Build and view the dashboard
bash scripts/publish.sh
# Then open .asv/html/index.html in a browser or Jupyter file browser
```

## HPC (Casper/Derecho)

```bash
# Submit slow benchmarks as a PBS job
qsub scripts/pbs_submit.sh
```

## Running a Specific Suite

```bash
# xESMF benchmarks only
asv run --bench "xesmf" HEAD

# Regridder creation only
asv run --bench "bench_regridder_creation" HEAD

# Quick mode: one rep per parameter combo (fast sanity check)
asv run --bench "xesmf" --quick HEAD
```

## Dashboard

```bash
asv publish          # build HTML from results/
asv preview          # serve dashboard locally (or just open .asv/html/index.html)
```

## Adding New Benchmarks

See [docs/adding_benchmarks.md](docs/adding_benchmarks.md).

## Environments

| Suite | Conda env | Python |
|---|---|---|
| xesmf, crocodash, e2e | `CrocoDash` | `/glade/work/manishrv/conda-envs/CrocoDash/bin/python` |
| mom6_forge | `mom6_forge` | `/glade/work/manishrv/conda-envs/mom6_forge/bin/python` |
