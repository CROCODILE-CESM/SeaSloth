# How SeaSloth Benchmarking Works

This document explains what actually happens when you run a benchmark — from invocation
through timing to the dashboard. No ASV prior knowledge assumed.

---

## The big picture

```
conda activate CrocoDash
bash scripts/run_bench.sh   # discovers CrocoDash commit → asv run --set-commit-hash <hash>
      │
      ▼
ASV reads asv.conf.json
      │
      ├─ "environment_type": "existing"  → use the currently active Python (CrocoDash env)
      ├─ "repo": "/path/to/CrocoDash"    → validate HEAD against CrocoDash git history
      │
      ├─ 1. Discover benchmarks (import every bench_*.py, find time_/track_/mem_ classes)
      ├─ 2. For each (class, method, param combo):
      │       spawn a subprocess in the active Python env
      │       → run benchmarks/__init__.py  (sets ESMFMKFILE)
      │       → call setup()               (excluded from timing)
      │       → time the method            (recorded)
      └─ 3. Write results/derecho/<croco-commit>-existing-py_<env>....json
```

**No conda env building.** `environment_type: "existing"` means ASV uses whatever Python
is currently active — it never creates or manages its own env. This is why you must
`conda activate CrocoDash` first.

**Results are tagged to CrocoDash commits**, not SeaSloth commits. The `"repo"` field in
`asv.conf.json` points to the CrocoDash git repository. ASV resolves `HEAD` and validates
commit hashes against CrocoDash's git history. The regression timeline on the dashboard
links back to CrocoDash commits on GitHub.

---

## First-time setup

No path configuration needed. `asv.conf.json` uses the public CrocoDash GitHub URL:

```json
"repo": "https://github.com/CROCODILE-CESM/CrocoDash"
```

This works on GLADE and in CI without any local path setup. Run `bash scripts/configure.sh`
to verify that CrocoDash and mom6_forge are importable in the active environment.

---

## `--set-commit-hash` — why it's required

With `environment_type: "existing"`, ASV has no git worktree to determine which commit
is being benchmarked. Without `--set-commit-hash`, ASV silently skips writing the result
file — benchmarks run but results are discarded.

Use `scripts/run_bench.sh` — it handles this automatically:
```bash
conda activate CrocoDash
bash scripts/run_bench.sh          # detects CrocoDash commit, passes --set-commit-hash
bash scripts/run_bench.sh --quick --bench "CrocoDashImports"
```

The script discovers the CrocoDash commit from your active editable install via
`CrocoDash.__file__` and runs `git rev-parse HEAD` there — so if you've checked out
an older CrocoDash commit locally, it tags the result to that commit, not GitHub's main.

---

## Params: the Cartesian product

Every benchmark class can have a `params` attribute — a list of lists. ASV computes the
full Cartesian product and runs the benchmark once per combination.

```python
class RegridderCreation:
    params = [
        [(100, 100), (300, 300), (600, 400)],        # src_size  — 3 values
        [(50, 50), (200, 200), (400, 300)],           # dst_size  — 3 values
        ["bilinear", "nearest_s2d", "conservative"],  # method    — 3 values
    ]
    param_names = ["src_size", "dst_size", "method"]
```

This produces 3 × 3 × 3 = **27 individual benchmark runs** for every `time_*` or `track_*`
method in the class.

---

## How a single benchmark run works

For each (method, param combo), ASV spawns a **fresh subprocess**:

```
subprocess starts (inside active CrocoDash Python env)
      │
      ├─ run benchmarks/__init__.py  (sets ESMFMKFILE; CrocoDash/mom6_forge are already
      │                               on sys.path via the editable install)
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

Each subprocess is isolated — a crash in one benchmark doesn't affect the others, and
memory from one run doesn't leak into the next.

### `setup()` — excluded from timing

`setup()` runs before the timing loop and is not measured. Put expensive construction here:

```python
def setup(self, src_size, dst_size, method):
    self.src = make_rect_grid(*src_size)
    self.dst = make_curvilinear_grid(*dst_size)
    # NOT timed — only time_* below is on the clock

def time_create_regridder(self, src_size, dst_size, method):
    xe.Regridder(self.src, self.dst, method=method)
```

### Timing mechanism

ASV uses Python's `timeit` internally. It runs the method multiple times and reports
statistics (mean ± std). The number of repetitions is chosen automatically to get a
stable measurement — fast operations get more reps, slow ones fewer.

`--quick` forces exactly **one repetition per param combo**. Results are noisier but the
run finishes much faster. Use `--quick` for sanity checks; omit it for real data.

### `teardown()` — cleanup after timing

Called after timing completes even if timing raised an error. Use it to remove temp files
or destroy ESMF objects:

```python
def teardown(self, src_size, dst_size, reuse_weights):
    shutil.rmtree(self._tmpdir, ignore_errors=True)
```

### Errors and skipped benchmarks

- `setup()` raises `NotImplementedError` → benchmark is marked **`n/a`** (skipped, not failed).
  Use this for data-dependent benchmarks when the required file is absent.
- `setup()` raises any other exception → benchmark is marked **failed** (red on dashboard).
- `time_*` raises an exception → benchmark is marked **failed**.

---

## Memory benchmarks

ASV has three memory benchmark types. SeaSloth uses `track_rss_mb` because ESMF makes
large C/Fortran heap allocations that `mem_*` and `peakmem_*` miss entirely.

| Type | What it measures | When to use |
|---|---|---|
| `mem_*` | Deep Python object size of the **return value** | Pure Python objects |
| `peakmem_*` | Peak `tracemalloc` usage during the call | Python heap only |
| `track_rss_mb` | Process RSS delta via psutil | C/Fortran allocations (ESMF, NetCDF) |

```python
def track_rss_mb(self, ...):
    import os, psutil
    proc = psutil.Process(os.getpid())
    before = proc.memory_info().rss
    xe.Regridder(...)
    return (proc.memory_info().rss - before) / 1024**2

track_rss_mb.unit = "MB"
```

---

## Results storage

After all benchmarks finish, ASV writes one JSON file per run:

```
results/
├── benchmarks.json                                           ← benchmark metadata
└── derecho/
    ├── machine.json                                          ← CPU/RAM/OS info
    └── <croco-commit>-existing-py_<env-path>.json           ← timing data
```

The file is named with the **CrocoDash commit hash** (from `--set-commit-hash`). This is
what links the dashboard timeline to CrocoDash's git history and makes `show_commit_url`
point to the right commit on GitHub.

If the process is killed mid-run (e.g., PBS walltime exceeded), the timing JSON is never
written. `machine.json` appears early; the timing file only appears at the very end.

Commit results to git so the history accumulates:

```bash
git add results/
git commit -m "bench: <brief description>"
git push
```

---

## `asv publish` and the dashboard

`scripts/publish.sh` runs two things:

1. **`asv publish`** — reads all JSON files in `results/`, resolves commit hashes against
   the CrocoDash git repo, and builds a self-contained HTML app in `.asv/html/`. Needs the
   full git history — this is why CI uses `fetch-depth: 0`.

2. **`scripts/generate_report.py`** — reads the same JSON files and generates snapshot bar
   charts (one per benchmark class) as a standalone `index.html`. Overwrites ASV's
   `index.html` and saves ASV's version as `asv_timeline.html`.

| Page | What it shows | Useful for |
|---|---|---|
| `index.html` | Bar charts per benchmark class (latest values) | Parameter sweeps, quick comparison |
| `asv_timeline.html` | Commit timeline, regression detection | Spotting regressions across versions |

The ASV timeline needs **2+ commits** with data before it shows anything meaningful.

---

## CI

The GitHub Actions workflow (`.github/workflows/benchmark.yml`) only runs `asv publish`
and `generate_report.py` — it never runs benchmarks. Benchmarks run on GLADE. Results are
committed to `results/` in git. CI checks out the repo with full history (`fetch-depth: 0`)
so ASV can resolve all CrocoDash commit hashes in the result files, then deploys to GitHub Pages.
