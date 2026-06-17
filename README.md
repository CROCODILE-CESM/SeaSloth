# CrocoScope

Performance benchmarking suite for the CROC ocean modeling ecosystem (CrocoDash, mom6_forge, xESMF/ESMF regridding).

## What's Benchmarked

| Suite | File(s) | Data needed | What it measures |
|---|---|---|---|
| xESMF weight generation | `xesmf/bench_weights_generate.py` | None (synthetic) | `xe.Regridder()` construction time + RSS, grid→grid and grid→locstream, up to ~1 M source points |
| xESMF regrid application | `xesmf/bench_regrid_apply.py` | None (synthetic) | `regridder(ds)` time across grid sizes, time depths, and methods |
| ESMF weight generation | `esmf/bench_weights_generate.py` | None (synthetic) | `esmpy.Regrid()` construction time + RSS — raw ESMF, same sizes as xESMF suite |
| ESMF regrid application | `esmf/bench_regrid_apply.py` | None (synthetic) | `esmpy.Regrid()(src, dst)` time — raw ESMF, loop over ntime steps |
| OBC forcing pipeline | `crocodash/bench_obc.py` | Cached GLORYS (GLADE) | REGRID + MERGE phases of `process_conditions()`, no GET; varies step_days chunk size |
| Runoff mapping | `mom6_forge/bench_runoff_mapping.py` | ESMF mesh files (GLADE) | `gen_rof_maps()` — nearest-neighbour and smoothed NN mapping between ROF and OCN meshes |
| Raw data access health | `crocodash/bench_raw_data_access.py` | Credentials / GLADE | Connectivity check for GLORYS (RDA + Copernicus), GEBCO, GLOFAS, MOM6 output; returns 1 (up) / 0 (down) |
| Bathymetry pipeline | `mom6_forge/bench_topo.py` | GEBCO (GLADE) | `Topo.set_from_dataset()` — GEBCO regrid + fill across grid sizes |

## Running Benchmarks

**Prerequisites:** the `CrocoDash` conda environment with `asv` installed (`pip install asv` once).

```bash
conda activate CrocoDash
python -m asv run
```

That's it. ASV uses the active environment directly — no env building step. Benchmarks that need data files (GEBCO, GLORYS, ESMF meshes) skip automatically if the files are absent.

To run a specific suite:
```bash
python -m asv run --bench "bench_raw_data_access"   # data access health checks
python -m asv run --bench "bench_weights_generate"  # weight generation only
python -m asv run --bench "XESMFWeightsGenerate"    # single class
```

On Derecho/GLADE, submit as a PBS job instead:
```bash
qsub scripts/pbs_submit.sh
```

After any run, commit results so the dashboard history accumulates:
```bash
git add results/
git commit -m "bench: <brief description>"
git push
```

## HPC data-dependent benchmarks

Fill in paths in `benchmarks/data_config.json` to enable these:

| Key | Benchmark | What to put |
|---|---|---|
| `gebco_path` | Bathymetry pipeline | Path to `GEBCO_2024.nc` |
| `mesh_pairs[*].rof_mesh` / `ocn_mesh` | Runoff mapping | Paths to ESMF mesh NetCDF files |
| `obc_config_path` | OBC pipeline | Path to a CrocoDash case config YAML |
| `obc_step_days_dirs` | OBC pipeline | Three pre-staged raw GLORYS folders (one per step_days) |

## Dashboard

```bash
bash scripts/publish.sh
# Opens .asv/html/index.html (commit timeline) and .asv/html/report.html (snapshot bar charts)
```

The live dashboard deploys to GitHub Pages on every push to `main`.
> **First-time setup:** Settings → Pages → Source → GitHub Actions.

## HPC data-dependent benchmarks

Benchmarks that need real data raise `NotImplementedError` in `setup()` when their files
are absent — ASV marks them as `n/a` and skips them. No manual commenting out needed.

For the OBC benchmark you need three pre-staged raw GLORYS directories (one per step_days
value) — download them once with `process_conditions(regrid=False, merge=False)` then
set the paths in `data_config.json`.

## Documentation

- [How benchmarking works](docs/how_benchmarking_works.md)
- [Adding new benchmarks](docs/adding_benchmarks.md)
