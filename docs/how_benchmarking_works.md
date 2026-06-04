# How CrocoScope Benchmarking Works

This document explains what actually happens when you run a benchmark — from invocation
through timing to the dashboard. No ASV prior knowledge assumed.

---

## The big picture

```
scripts/run_fast.sh
      │
      ▼
asv run --python <env> --bench "xesmf" --quick
      │
      ├─ 1. Discover benchmarks (import every bench_*.py, find classes)
      ├─ 2. For each (class, method, param combo):
      │       spawn a subprocess → run setup() → time the method → record result
      └─ 3. Write results/<machine>/<commit>-<timestamp>.json

asv publish
      │
      └─ Read all result JSON files → build .asv/html/index.html + data files
```

---

## Step 1 — Discovery

ASV recursively imports every Python file under `benchmarks/` whose name starts with
`bench_`. It looks for classes whose methods start with `time_`, `mem_`, or `track_`.
Each such method becomes one benchmark.

The full list of discovered benchmarks is stored in `results/benchmarks.json` (the
metadata file — not timing data).

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

This produces 3 × 3 × 3 = **27 individual benchmark runs** for every `time_*` or `mem_*`
method in that class. Each run is independent — separate subprocess, separate timing.

---

## Step 3 — How a single benchmark run works

For each (method, param combo), ASV does the following in a **fresh subprocess**:

```
subprocess starts
      │
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

This captures the weight matrix stored inside the Regridder (a scipy sparse array in
Python memory). It does **not** capture ESMF's C/Fortran heap allocations.

**Common mistake:** forgetting the `return`. ASV sees `None` and reports 0.

### `peakmem_*` — peak tracemalloc during the call

ASV wraps the method with `tracemalloc` and records the highest Python heap usage
reached during execution. No return value needed.

```python
def peakmem_apply(self, ...):
    self.regridder(self.src_data)   # no return — tracemalloc captures the peak
```

Use this when the interesting memory is **transient** — temporary arrays created during
a computation (e.g., the intermediate arrays in a sparse matrix–vector multiply).
Like `mem_*`, it only sees Python heap allocations, not C-level memory.

### `track_*` — custom numeric metric

Returns any number you compute yourself. Use with `psutil` when you need true process
RSS (captures C/Fortran allocations that tracemalloc misses):

```python
def track_rss_mb(self, ...):
    import psutil, os, gc
    gc.collect()
    proc = psutil.Process(os.getpid())
    before = proc.memory_info().rss
    xe.Regridder(...)
    return (proc.memory_info().rss - before) / 1024**2

track_rss_mb.unit = "MB"
```

**In CrocoScope:** creation benchmarks use `mem_*` (weight matrix size) and application
benchmarks use `peakmem_*` (temporary array peak). If you need to capture ESMF's actual
C-level memory footprint, add a `track_rss_mb` method.

---

## Step 5 — Errors and skipped benchmarks

If `setup()` raises `NotImplementedError`, ASV marks the benchmark as **`n/a`** (not
applicable) and moves on. This is how CrocoScope marks HPC-only benchmarks that can't
run without GLORYS or GEBCO data:

```python
def setup(self, n_workers, step_days):
    raise NotImplementedError("Requires HPC GLORYS data — run via scripts/pbs_submit.sh")
```

If a `time_*` or `mem_*` method raises any exception, ASV marks it as **failed** (shown
in red on the dashboard). The run continues with the next combination.

If `setup()` raises any other exception (not NotImplementedError), it's a **failed** run,
not `n/a`.

---

## Step 6 — Results storage

After all benchmarks finish, ASV writes one JSON file per run:

```
results/
├── benchmarks.json                          ← benchmark metadata (params, units, code)
└── crlogin2/                                ← one dir per machine
    ├── machine.json                         ← CPU/RAM/OS info
    └── <commit-hash>-existing-<ts>.json     ← timing data for this commit+run
```

The commit hash is the current git HEAD at the time of the run. This is how the dashboard
builds a timeline — each result file is one point on the x-axis.

**Important:** if the ASV process is killed before it finishes (e.g., login node OOM kill),
the timing JSON is never written. `machine.json` appears early; the timing file appears only
at the end of the run.

---

## Step 7 — `asv publish` and the dashboard

`asv publish` reads **all** JSON files in `results/` — from every machine, every commit —
and builds a self-contained HTML site in `.asv/html/`.

The dashboard has three views:
- **Grid view** — one cell per benchmark, colored by speed relative to baseline
- **List view** — sortable table of all benchmarks and their latest timings
- **Regressions** — benchmarks where a recent commit was detectably slower

The dashboard compares across commits on the x-axis. With a single commit (first run),
the timeline has one point and there's nothing to compare — the grid shows timings but no
regression arrows. Historical data accumulates as you commit more results.

---

## Environment mode: why there are no commit checkouts

Standard ASV creates its own virtualenvs and checks out different commits to compare
performance across your git history. CrocoScope uses `environment_type: "existing"` in
`asv.conf.json` instead, for two reasons:

1. ESMF cannot be pip-installed — it requires a compiled library (either via conda-forge
   or an HPC module system). ASV's managed envs can't handle this.
2. The CrocoDash and mom6_forge conda environments are large and pre-built; recreating
   them inside ASV would be impractical.

With `environment_type: "existing"`, ASV skips the checkout step and benchmarks whatever
code is currently installed in the env you point at with `--python`. You lose the
automatic commit-to-commit regression detection, but gain full compatibility with complex
HPC environments.

---

## Quick reference: what each script does

| Script | What it runs | When to use |
|---|---|---|
| `scripts/run_fast.sh` | `asv run --bench "xesmf" --quick` | Quick sanity check on any node |
| `scripts/run_full.sh` | xesmf (full) + mom6_forge fast suites | Casper interactive node |
| `scripts/pbs_submit.sh` | mom6_forge topo + crocodash OBC | PBS job, needs GEBCO/GLORYS |
| `scripts/publish.sh` | `asv publish` | After any run, to rebuild dashboard |

After any HPC run, commit the results before rebuilding the dashboard so they're
included in version history:

```bash
git add results/
git commit -m "add HPC benchmark results: <brief description>"
git push
```
