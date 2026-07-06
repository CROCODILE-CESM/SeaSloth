#!/usr/bin/env python3
"""
check_data_access.py — Data-access health check: HTTP link reachability
and raw-function validation (validate_function) for every registered
CrocoDash product.

Always runs:
  • Link checks — HTTP HEAD/GET on URLs in benchmarks/link_config.json

Also runs when CrocoDash is importable (i.e. on GLADE/Derecho with the
CrocoDash conda env active):
  • validate_function — toy-calls every registered access method via
    ProductRegistry.validate_function().

Writes a single results/health.json, always overwritten — this is a
snapshot of current status, not a history.

Usage
-----
    conda run -n CrocoDash python scripts/check_data_access.py
"""

import concurrent.futures
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

REPO_ROOT = Path(__file__).resolve().parent.parent
CONFIG_FILE = REPO_ROOT / "benchmarks" / "link_config.json"
OUTPUT_FILE = REPO_ROOT / "results" / "health.json"

LINK_TIMEOUT = 20
VALIDATE_TIMEOUT = 60  # seconds per validate_function call


def _check_link(url):
    """HEAD with GET fallback. Returns (ok: bool, elapsed_seconds)."""
    t0 = time.monotonic()
    try:
        r = requests.head(url, allow_redirects=True, timeout=LINK_TIMEOUT)
        if r.status_code == 200:
            return True, time.monotonic() - t0
    except Exception:
        pass
    t0 = time.monotonic()
    try:
        r = requests.get(url, stream=True, allow_redirects=True, timeout=LINK_TIMEOUT)
        next(r.iter_content(chunk_size=1), None)
        return r.status_code == 200, time.monotonic() - t0
    except Exception:
        return False, time.monotonic() - t0


def run_link_checks(products):
    rows = []
    for product, url in sorted(products.items()):
        ok, elapsed = _check_link(url)
        rows.append({"product": product, "url": url, "ok": ok, "elapsed_s": round(elapsed, 2)})
        print(f"  link  [{'OK  ' if ok else 'FAIL'}] {product}: {url}  ({elapsed:.1f}s)")
    return rows


def _try_import_crocodash():
    try:
        from CrocoDash.raw_data_access.datasets import load_all_datasets
        from CrocoDash.raw_data_access.registry import ProductRegistry

        load_all_datasets()
        return ProductRegistry
    except Exception as exc:
        print(f"  CrocoDash not importable ({exc.__class__.__name__}: {exc})")
        print("  Skipping validate_function checks.")
        return None


def _call_with_timeout(fn, timeout_s):
    """Run fn() in a thread; return elapsed or raise TimeoutError.

    Enforces a wall-clock cap on validate_function calls that may block
    indefinitely on network I/O (e.g. CDS API, SVN endpoints).
    """
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
        future = ex.submit(fn)
        t0 = time.monotonic()
        try:
            future.result(timeout=timeout_s)
            return time.monotonic() - t0
        except concurrent.futures.TimeoutError:
            raise TimeoutError(f"exceeded {timeout_s}s")


def run_validate_checks(registry):
    """Calls validate_function for every registered (product, method) pair."""
    rows = []
    for product in sorted(registry.list_products()):
        for method in sorted(registry.list_access_methods(product)):
            status = "OK  "
            ok = True
            try:
                elapsed = _call_with_timeout(
                    lambda p=product, m=method: registry.validate_function(p, m),
                    VALIDATE_TIMEOUT,
                )
            except TimeoutError:
                ok, elapsed, status = False, VALIDATE_TIMEOUT, "TIME"
            except Exception:
                ok, elapsed, status = False, 0.0, "FAIL"
            rows.append(
                {"product": product, "method": method, "ok": ok, "elapsed_s": round(elapsed, 2)}
            )
            print(f"  func  [{status}] {product} / {method}  ({elapsed:.1f}s)")
    return rows


def main():
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    cfg = json.loads(CONFIG_FILE.read_text())
    products = cfg.get("products", {})

    print("=== Link checks ===")
    link_checks = run_link_checks(products)
    link_ok = sum(1 for r in link_checks if r["ok"])

    print("\n=== validate_function checks ===")
    validate_checks = []
    registry = _try_import_crocodash()
    if registry is not None:
        validate_checks = run_validate_checks(registry)
    val_ok = sum(1 for r in validate_checks if r["ok"])

    data = {
        "date": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "link_checks": link_checks,
        "validate_checks": validate_checks,
    }
    OUTPUT_FILE.write_text(json.dumps(data, indent=2))
    print(f"\nResults written to {OUTPUT_FILE}")

    print(f"\nLinks:    {link_ok}/{len(link_checks)} OK")
    if validate_checks:
        print(f"Functions:{val_ok}/{len(validate_checks)} OK")
    else:
        print("Functions: skipped (CrocoDash not available)")

    any_fail = link_ok < len(link_checks) or (
        validate_checks and val_ok < len(validate_checks)
    )
    if any_fail:
        sys.exit(1)


if __name__ == "__main__":
    main()
