#!/usr/bin/env python3
"""
check_links.py — Run HTTP link checks for registered data products and write
ASV-format results to results/github-ci/.

Reads product URLs from benchmarks/link_config.json (no CrocoDash needed).
Intended for daily CI where esmpy/CrocoDash are not available.

Run from repo root:
    python scripts/check_links.py
    # then regenerate the health page:
    python scripts/generate_health_page.py
"""

import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import requests

REPO_ROOT = Path(__file__).resolve().parent.parent
CONFIG_FILE = REPO_ROOT / "benchmarks" / "link_config.json"
CI_DIR = REPO_ROOT / "results" / "github-ci"
MACHINE_FILE = CI_DIR / "machine.json"
LINK_KEY = "crocodash.bench_raw_data_access.DataAccessLinkCheck.track_link_ok"
TIMEOUT = 20


def _check_link(url):
    """HEAD with GET-stream fallback; returns (1.0, elapsed) or (0.0, elapsed)."""
    t0 = time.monotonic()
    try:
        r = requests.head(url, allow_redirects=True, timeout=TIMEOUT)
        elapsed = time.monotonic() - t0
        if r.status_code == 200:
            return 1.0, elapsed
    except Exception:
        pass
    t0 = time.monotonic()
    try:
        r = requests.get(url, stream=True, allow_redirects=True, timeout=TIMEOUT)
        next(r.iter_content(chunk_size=1), None)
        elapsed = time.monotonic() - t0
        return (1.0 if r.status_code == 200 else 0.0), elapsed
    except Exception:
        return 0.0, time.monotonic() - t0


def main():
    cfg = json.loads(CONFIG_FILE.read_text())
    products = cfg.get("products", {})
    if not products:
        print("No products in link_config.json", file=sys.stderr)
        sys.exit(1)

    CI_DIR.mkdir(parents=True, exist_ok=True)

    if not MACHINE_FILE.exists():
        MACHINE_FILE.write_text(
            json.dumps(
                {
                    "arch": "x86_64",
                    "cpu": "GitHub Actions",
                    "machine": "github-ci",
                    "num_cpu": 2,
                    "os": "Linux",
                    "ram": 7,
                },
                indent=2,
            )
        )

    # Sorted to match the order ASV would produce (and for stable diffs)
    param_combos = sorted(products.items())
    params = [[f"'{p}'" for p, _ in param_combos]]
    results = []
    total_elapsed = 0.0
    any_fail = False

    print(f"Checking {len(param_combos)} product links…")
    for product, url in param_combos:
        ok, elapsed = _check_link(url)
        results.append(ok)
        total_elapsed += elapsed
        any_fail = any_fail or (ok != 1.0)
        status = "OK  " if ok == 1.0 else "FAIL"
        print(f"  [{status}] {product}: {url}  ({elapsed:.1f}s)")

    now_ms = int(time.time() * 1000)
    date_str = datetime.utcnow().strftime("%Y%m%d")

    result_data = {
        "commit_hash": f"ci-{date_str}",
        "date": now_ms,
        "params": {},
        "python": "github-actions",
        "requirements": {},
        "results": {
            LINK_KEY: [
                results,
                params,
                f"ci-link-{date_str}",
                now_ms,
                total_elapsed,
            ]
        },
        "env_name": "github-actions-link-check",
        "version": 2,
    }

    out_file = CI_DIR / f"ci-{date_str}-link-check.json"
    out_file.write_text(json.dumps(result_data, indent=2))

    ok_count = sum(1 for v in results if v == 1.0)
    print(f"\n{ok_count}/{len(results)} links OK")
    print(f"Results written to {out_file}")

    if any_fail:
        sys.exit(1)


if __name__ == "__main__":
    main()
