# Adding New Benchmarks to SeaSloth

## Which file to edit

| What you're benchmarking | Directory | Status |
|---|---|---|
| xESMF / ESMF regridding | `benchmarks/xesmf/` | Implemented |
| mom6_forge Grid kdtree | `benchmarks/mom6_forge/bench_grid_kdtree.py` | Implemented |
| mom6_forge Grid metrics | `benchmarks/mom6_forge/bench_grid_metrics.py` | Implemented |
| mom6_forge topo regrid | `benchmarks/mom6_forge/bench_topo_regrid.py` | Implemented |
| mom6_forge topo tidy | `benchmarks/mom6_forge/bench_topo_tidy.py` | Implemented |
| mom6_forge regrid subsampling | `benchmarks/mom6_forge/bench_regrid_subsampling.py` | Implemented |
| CrocoDash GLORYS download throughput | `benchmarks/crocodash/bench_raw_data_access.py` | Implemented |
| CrocoDash OBC forcing pipeline | `benchmarks/crocodash/bench_obc.py` | Stub (needs GLORYS) |

## Benchmark class anatomy

```python
class MyBenchmark:
    # Cartesian product of all params — each combo gets its own timing run
    params = [
        [100, 300, 600],              # first parameter
        ["bilinear", "conservative"], # second parameter
    ]
    param_names = ["grid_size", "method"]
    timeout = 300  # seconds; increase for slow benchmarks

    def setup(self, grid_size, method):
        # Runs BEFORE timing — expensive setup goes here (excluded from measurement)
        from mom6_forge.grid import Grid
        self.grid = Grid(lenx=10.0, leny=10.0, nx=grid_size, ny=grid_size)

    def time_my_operation(self, grid_size, method):
        # Anything in a time_* method is timed
        do_the_thing(self.grid, method=method)

    def track_rss_mb(self, grid_size, method):
        # Returns a custom scalar (MB/s, MB, count, etc.)
        import os, psutil
        proc = psutil.Process(os.getpid())
        before = proc.memory_info().rss
        do_the_thing(self.grid, method=method)
        return (proc.memory_info().rss - before) / 1024**2

    track_rss_mb.unit = "MB"  # shown on dashboard Y-axis

    def teardown(self, grid_size, method):
        # Optional cleanup (temp files, etc.)
        pass
```

## Importing mom6_forge and CrocoDash

These packages are not on conda-forge, so they're not in the ASV conda env by default.
`benchmarks/__init__.py` adds their source roots to `sys.path` automatically by reading
`benchmarks/data_config.json`:

```json
{
    "mom6_forge_src": "/glade/u/home/manishrv/documents/croc/regional_mom_workflows/mom6_forge",
    "crocodash_src": "/glade/u/home/manishrv/documents/croc/regional_mom_workflows/CrocoDash"
}
```

Put your imports **inside `setup()` or `time_*()`** rather than at the module top level
so that a missing package shows as `n/a` rather than failing the whole file:

```python
def setup(self, grid_size):
    from mom6_forge.grid import Grid      # imported here, not at module top
    self.grid = Grid(lenx=10.0, leny=10.0, nx=grid_size, ny=grid_size)
```

If the import is at module level (as in the xesmf benchmarks), make sure the package
is in the `matrix` in `asv.conf.json`.

## Data-dependent benchmarks

If your benchmark needs a data file (GEBCO, GLORYS), read the path from
`benchmarks/data_config.json` via the helper:

```python
from benchmarks.common.config import get_path

def setup(self, ...):
    gebco = get_path("gebco_path")
    if not gebco or not __import__("pathlib").Path(gebco).exists():
        raise NotImplementedError(f"GEBCO not found at {gebco!r}")
    self._gebco = gebco
```

`raise NotImplementedError` in `setup()` marks the benchmark as `n/a` on the dashboard
instead of failing. Edit `benchmarks/data_config.json` to update paths for your system.

Currently configured paths:

| Key | Default path | Used by |
|---|---|---|
| `gebco_path` | `/glade/derecho/scratch/manishrv/.../GEBCO_2024.nc` | `bench_topo_regrid.TopoSetFromDataset` |
| `glorys_rda_path` | `/glade/campaign/collections/rda/data/d010049/` | `bench_raw_data_access.GLORYSRDAThroughput` |
| `mom6_forge_src` | `/glade/.../mom6_forge` | `benchmarks/__init__.py` sys.path |
| `crocodash_src` | `/glade/.../CrocoDash` | `benchmarks/__init__.py` sys.path |

## Synthetic data

Use helpers from `benchmarks/common/synthetic_data.py`:

| Function | Returns | Use for |
|---|---|---|
| `make_rect_grid(nlon, nlat)` | xr.Dataset with 1D lon/lat + bounds | xESMF source; `regrid_with_subsampling` input |
| `make_curvilinear_grid(nlon, nlat)` | xr.Dataset with 2D lon/lat + bounds | xESMF destination |
| `make_locstream_grid(n)` | xr.Dataset with 1D ncells | OBC boundary (locstream_out=True) |
| `make_data_variable(grid, ntime, nvars)` | grid + data vars | Anything needing actual data to regrid |

For mom6_forge Grid benchmarks, construct `Grid` directly — do not use `make_supergrid`:

```python
from mom6_forge.grid import Grid
grid = Grid(lenx=10.0, leny=10.0, nx=nx, ny=ny, xstart=0.0, ystart=0.0)
```

## Fast vs. slow classification

| Suite | Fast? | Reason |
|---|---|---|
| mom6_forge grid/kdtree/tidy/subsampling | Yes — `run_fast.sh` | Pure Python/numpy/scipy, no ESMF |
| xesmf creation (weight gen) | No — `run_full.sh` | ESMF C library weight computation |
| xesmf application | Moderate — `run_full.sh` | Fast per-call but many param combos |
| topo regrid with GEBCO | Slow — `pbs_submit.sh` | Large file + ESMF |
| GLORYS download throughput | Slow — `pbs_submit.sh` | Network/I/O bound |
| OBC pipeline | Very slow — `pbs_submit.sh` | Full forcing pipeline |

## Running your new benchmark

```bash
conda activate CrocoDash

# Quick sanity check (one rep per combo — fast but noisy)
python -m asv run --bench "MyBenchmark" --quick --set-commit-hash HEAD

# Full timing (adaptive reps — use for real data)
python -m asv run --bench "MyBenchmark" --set-commit-hash HEAD

# Build dashboard
bash scripts/publish.sh
```

**Always pass `--set-commit-hash HEAD`.** With `environment_type: "existing"`, ASV silently
skips writing result files unless this flag is set.

`HEAD` resolves to the current CrocoDash commit — `asv.conf.json` `"repo"` is the public
CrocoDash GitHub URL, so no local path setup is needed.

## Committing results

Results are stored as JSON in `results/derecho/`. Commit them — they are the historical
record that makes the dashboard timeline work:

```bash
git add results/
git commit -m "add MyBenchmark results: <what changed>"
git push
```

## Updating existing benchmarks

If you change a `params` list or rename a benchmark class, ASV treats it as a new
benchmark and loses the historical comparison. That's fine — note it in the commit
message so the timeline discontinuity is explained.
