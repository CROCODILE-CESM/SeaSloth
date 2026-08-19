#!/usr/bin/env python3
"""
merge_results.py — Merge one pytest-benchmark JSON into results/latest.json.

`run_benchmarks.sh` writes `--benchmark-json=results/latest.json`, which means a
partial run (`-k xesmf`, one suite, one new benchmark file) *replaces* the whole
snapshot rather than updating it — silently dropping every suite that wasn't part
of that run. Suites here have very different data and hardware requirements (the
40 deg GEBCO sweep needs ~90 GB; the runoff-mapping sweep needs the `mom6_forge`
env), so re-running everything together just to refresh one suite isn't practical.

This merges instead: benchmarks are keyed by `fullname`, incoming entries replace
same-named ones, and everything else in the base file is left alone.

Usage:
    python scripts/merge_results.py <new-results.json>
    python scripts/merge_results.py <new-results.json> --into results/other.json

Because a merged file holds runs from more than one session, the top-level
`machine_info`/`commit_info`/`datetime` no longer describe every benchmark in it.
Each incoming benchmark therefore carries its own run's `datetime` and node name
in `extra_info` (`run_datetime`, `run_node`), so provenance survives the merge.
"""

import argparse
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_BASE = REPO_ROOT / "results" / "latest.json"


def merge(base, incoming):
    """Return base with incoming's benchmarks merged in, keyed by fullname."""
    run_datetime = incoming.get("datetime")
    run_node = incoming.get("machine_info", {}).get("node")

    by_name = {bm["fullname"]: bm for bm in base.get("benchmarks", [])}
    added, replaced = 0, 0
    for bm in incoming.get("benchmarks", []):
        bm.setdefault("extra_info", {})
        bm["extra_info"]["run_datetime"] = run_datetime
        bm["extra_info"]["run_node"] = run_node
        if bm["fullname"] in by_name:
            replaced += 1
        else:
            added += 1
        by_name[bm["fullname"]] = bm

    base["benchmarks"] = sorted(by_name.values(), key=lambda b: b["fullname"])
    return base, added, replaced


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("new_results", help="pytest-benchmark JSON to merge in")
    parser.add_argument(
        "--into",
        default=str(DEFAULT_BASE),
        help=f"base JSON to merge into (default: {DEFAULT_BASE})",
    )
    args = parser.parse_args()

    incoming_path = Path(args.new_results)
    base_path = Path(args.into)

    with open(incoming_path) as f:
        incoming = json.load(f)

    if base_path.exists():
        with open(base_path) as f:
            base = json.load(f)
    else:
        # Nothing to merge into — the incoming run becomes the snapshot, and its
        # own metadata is the right top-level metadata for it.
        base = {k: v for k, v in incoming.items() if k != "benchmarks"}
        base["benchmarks"] = []

    merged, added, replaced = merge(base, incoming)

    base_path.parent.mkdir(parents=True, exist_ok=True)
    with open(base_path, "w") as f:
        json.dump(merged, f, indent=2)

    print(
        f"Merged {incoming_path} -> {base_path}: "
        f"{added} added, {replaced} replaced, "
        f"{len(merged['benchmarks'])} total"
    )


if __name__ == "__main__":
    main()
