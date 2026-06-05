# How CrocoScope Benchmarking Works

This document explains what actually happens when you run a benchmark — from invocation
through timing to the dashboard. No ASV prior knowledge assumed.

---

## The big picture

```
scripts/run_fast.sh   (or run_full.sh / pbs_submit.sh)
      │
      ▼
/path/to/CrocoDash/bin/python -m asv run --bench "..." --quick HEAD
      │
      ├─ 1. Discover benchmarks (import every bench_*.py, find classes)
      ├─ 2. Checkout CrocoScope at HEAD into a temp worktree
      ├─ 3. For each (class, method, param combo):
      │       spawn a subprocess in the ASV conda env
      │       → run benchmarks/__init__.py  (sets ESMFMKFILE + sys.path)
      │       → run setup()                 (excluded from timing)
      │       → time the method             (recorded)
      └─ 4. Write results/derecho/<commit>-conda-py3.11-....json
```

`HEAD` tells ASV to benchmark the current git commit. Results are tagged with that
commit hash and saved to disk. This is the only range spec that works with
`environment_type: "conda"`.

---

## What ASV manages vs. what the scripts manage

| Thing | Who manages it |
|---|---|
| `env/` — conda env with numpy/xarray/xesmf/etc. | ASV (built once, reused) |
| mom6_forge, CrocoDash imports | `benchmarks/__init__.py` via `sys.path` from `data_config.json` |
| ESMFMKFILE | `benchmarks/__init__.py` (glob inside `env/`) |
| Which Python runs `asv` | The scripts (`/glade/work/.../CrocoDash/bin/python`) |
| Which Python runs benchmarks | ASV's managed conda env |

The CrocoDash Python is only used to invoke the `asv` CLI — it is not the Python that
runs your benchmark code. Benchmark code runs inside `env/`.

---

## Step 1 — Discovery

ASV recursively imports every Python file under `benchmarks/` whose name starts with
`bench_`. It looks for classes whose methods start with `time_`, `mem_`, `peakmem_`, or `track_`.
Each such method becomes one benchmark.

Discovery runs `benchmarks/__init__.py` first — this sets `ESMFMKFILE` and adds
mom6_forge/CrocoDash source roots to `sys.path` so those packages can be imported
inside the ASV conda env.

---

## Step 2 — Params: the Cartesian product

Every benchmark class can have a `params` attribute — a list of lists. ASV computes the
full Cartesian product and runs the benchmark once per combination.

```python
class RegridderCreation:
    params = [
        [(100, 100), (300, 300), (600, 400)],   # src_size  — 3 values
        [(50, 50), (200, 200), (400, 300)],      # dst_size  — 3 values
        ["bilinear", "nearest_s2d", "conservative"],  # method — 3 values
    ]
    param_names = ["src_size", "dst_size", "method"]
```

This produces 3 × 3 × 3 = **27 individual benchmark runs** for every `time_*` or `track_*`
method in that class.

---

## Step 3 — How a single benchmark run works

For each (method, param combo), ASV does the following in a **fresh subprocess**:

```
subprocess starts (inside ASV conda env)
      │
      ├─ import benchmarks (runs __init__.py → ESMFMKFILE + sys.path set)
      ├─ import the benchmark module
      ├─ instantiate the class
      ├─ call setup(params...)          ← excluded from timing
      │
      └─ TIMING LOOP:
            repeat N times {
                call time_my_method(params...)   ← only this is timed
            }
            record: min, mean, std of N reps
```

The subprocess isolation means:
- A crash in one benchmark doesn't affect others
- Memory from one run doesn't leak into the next
- Each run starts with a clean Python interpreter

### What `setup()` is for

`setup()` runs before timing begins and is **not included in the measurement**. Put
anything expensive that you want to exclude — building grids, constructing regridders,
loading data. Only the `time_*` method body is on the clock.

```python
def setup(self, src_size, dst_size, method):
    # NOT timed — build grids here
    self.src = make_rect_grid(*src_size)
    self.dst = make_curvilinear_grid(*dst_size)

def time_create_regridder(self, src_size, dst_size, method):
    # TIMED — only this call is measured
    xe.Regridder(self.src, self.dst, method=method, ...)
```

### The timing mechanism

ASV uses Python's `timeit` module internally. It runs the method multiple times
and reports statistics (min/mean/std). The number of repetitions is chosen automatically
to get a stable measurement — fast operations get more reps, slow ones fewer.

`--quick` mode forces exactly **one repetition per param combo** and skips the warmup
phase. Results are less statistically reliable but the run finishes much faster. Use it
for sanity checks; use full runs (no `--quick`) for real data.

### `teardown()` — cleanup after timing

If a benchmark creates temp files or other side effects, `teardown()` runs after timing
completes (still in the same subprocess). ASV calls it even if the timing raised an error.

```python
def teardown(self, src_size, dst_size, reuse_weights):
    shutil.rmtree(self._tmpdir, ignore_errors=True)
```

---

## Step 4 — Memory benchmarks: three conventions

ASV has three distinct memory benchmark types. **They work very differently** and it's
easy to get zeros if you use the wrong one.

### `mem_*` — size of the return value

ASV calls the method and measures the deep Python object size of what it **returns**
(using `sys.getsizeof` recursively). If the method returns `None`, the result is 0.

```python
def mem_create_regridder(self, ...):
    return xe.Regridder(...)   # MUST return the object — ASV measures its size
```

**Common mistake:** forgetting the `return`. ASV sees `None` and reports 0.

### `peakmem_*` — peak tracemalloc during the call

ASV wraps the method with `tracemalloc` and records the highest Python heap usage
reached during execution. No return value needed. Only sees Python heap — misses C/Fortran.

### `track_rss_mb` — custom RSS metric (what CrocoScope uses)

Returns process RSS delta measured with psutil — captures C/Fortran heap allocations
(ESMF, NetCDF, HDF5) that `mem_*` and `peakmem_*` miss entirely.

```python
def track_rss_mb(self, ...):
    import os, psutil
    proc = psutil.Process(os.getpid())
    before = proc.memory_info().rss
    xe.Regridder(...)          # call being measured
    return (proc.memory_info().rss - before) / 1024**2

track_rss_mb.unit = "MB"
```

---

## Step 5 — Errors and skipped benchmarks

If `setup()` raises `NotImplementedError`, ASV marks the benchmark as **`n/a`** (not
applicable) and moves on. This is how CrocoScope marks data-dependent benchmarks that
can't run without GLORYS or GEBCO:

```python
def setup(self, dst_size):
    gebco = get_path("gebco_path")
    if not gebco or not Path(gebco).exists():
        raise NotImplementedError(f"GEBCO not found at {gebco!r}")
```

If `setup()` raises any other exception, it's a **failed** run (shown in red), not `n/a`.

---

## Step 6 — Results storage

After all benchmarks finish, ASV writes one JSON file per run:

```
results/
├── benchmarks.json                                    ← benchmark metadata
└── derecho/                                           ← one dir per machine
    ├── machine.json                                   ← CPU/RAM/OS info
    └── <commit>-conda-py3.11-numpy-psutil-....json   ← timing data
```

The commit hash comes from CrocoScope's own git HEAD at run time. The dashboard X-axis
is CrocoScope commits — not CrocoDash or mom6_forge commits. To track performance of
those packages over time, run benchmarks after each change and commit the results with
a descriptive message.

**If the process is killed mid-run** (e.g., login node OOM), the timing JSON is never
written and the run is lost. `machine.json` appears early; the timing file only appears
at the end.

---

## Step 7 — `asv publish` and the dashboard

`asv publish` reads **all** JSON files in `results/` and builds a self-contained HTML
site in `.asv/html/`. The dashboard has three views:

- **Grid** — one cell per benchmark, colored by speed relative to baseline
- **List** — sortable table with latest timings
- **Regressions** — benchmarks where a recent commit was detectably slower

`asv publish` needs the full git history to resolve commit hashes to dates and messages.
This is why the CI workflow uses `fetch-depth: 0` — a shallow clone produces an empty
dashboard.

---

## Script reference

| Script | What it runs | When to use |
|---|---|---|
| `scripts/run_fast.sh` | mom6_forge grid/kdtree/tidy/subsampling (`--quick`) | Quick sanity check on any node |
| `scripts/run_full.sh` | All benchmarks including xesmf (full timing) | Casper interactive node |
| `scripts/pbs_submit.sh` | All benchmarks including data-dependent ones | PBS job; needs GEBCO/GLORYS |
| `scripts/publish.sh` | `asv publish` | After any run, to rebuild dashboard |

xesmf benchmarks (ESMF weight generation) are **not** in `run_fast.sh` — they are slow
even with `--quick` and should be run via `run_full.sh` or `pbs_submit.sh`.

After any run, commit results before rebuilding the dashboard:

```bash
git add results/
git commit -m "add benchmark results: <brief description of what changed>"
git push
```
