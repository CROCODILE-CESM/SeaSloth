# Adding New Benchmarks to CrocoScope

## Which file to edit

| What you're benchmarking | Directory |
|---|---|
| xESMF / ESMF regridding | `benchmarks/xesmf/` |
| mom6_forge Grid/Topo/mapping ops | `benchmarks/mom6_forge/` |
| CrocoDash forcing pipeline (OBC, BGC, tides) | `benchmarks/crocodash/` |
| End-to-end Case workflow | `benchmarks/e2e/` |

## Benchmark class anatomy

```python
class MyBenchmark:
    # Cartesian product of all params — each combo gets its own timing run
    params = [
        [100, 300, 600],   # first parameter
        ["bilinear", "conservative"],  # second parameter
    ]
    param_names = ["grid_size", "method"]
    timeout = 300  # seconds; increase for slow benchmarks

    def setup(self, grid_size, method):
        # Runs BEFORE timing — expensive setup goes here (excluded from measurement)
        self.data = make_rect_grid(grid_size, grid_size)

    def time_my_operation(self, grid_size, method):
        # Anything in a time_* method is timed
        do_the_thing(self.data, method=method)

    def mem_my_operation(self, grid_size, method):
        # Same body as time_* — ASV wraps this with tracemalloc for peak memory
        do_the_thing(self.data, method=method)

    def teardown(self, grid_size, method):
        # Optional cleanup (e.g., delete temp files)
        pass
```

## CI/local vs HPC — how to mark

Add a docstring at the top of each file:

```
CI/local: safe — no file I/O, synthetic data only.
```

or

```
HPC: requires /glade/derecho/scratch/.../GEBCO_2024.nc
     Run via scripts/pbs_submit.sh
```

If a benchmark requires data that won't exist in CI, raise `NotImplementedError` in `setup()` — ASV will mark the result as `n/a` rather than erroring the whole run.

## Synthetic data

Use helpers from `benchmarks/common/synthetic_data.py`:

| Function | Returns | Use for |
|---|---|---|
| `make_rect_grid(nlon, nlat)` | xr.Dataset with 1D lon/lat | xESMF source grids |
| `make_curvilinear_grid(nlon, nlat)` | xr.Dataset with 2D lon/lat | xESMF destination grids |
| `make_locstream_grid(n)` | xr.Dataset with 1D ncells | OBC boundary (locstream_out=True) |
| `make_data_variable(grid, ntime, nvars)` | xr.Dataset with data vars | Anything that needs actual data to regrid |
| `make_supergrid(nx, ny)` | xr.Dataset matching MOM6 supergrid layout | mom6_forge Grid construction |

## Running your new benchmark

```bash
# Quick sanity check (one rep per param combo, saves results)
asv run --bench "MyBenchmark" --quick EXISTING

# Full timing (saves results)
asv run --bench "MyBenchmark" EXISTING

# Build dashboard
bash scripts/publish.sh
```

## Results

Results are stored as JSON in `results/`. Commit them — they're the historical
record that makes the dashboard's timeline view work.

```bash
git add results/
git commit -m "add MyBenchmark results"
```

## Updating existing benchmarks

If you change a `params` list or rename a benchmark class, ASV treats it as a new
benchmark and loses the historical comparison. That's fine — just note it in the
commit message so the timeline discontinuity is explained.
