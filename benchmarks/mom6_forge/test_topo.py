"""
Benchmarks: Topo.set_from_dataset() (mom6_forge).

Full bathymetry processing pipeline: read GEBCO, regrid to the model grid,
apply depth filters and fill algorithms.

The primary cost driver is domain extent, not destination resolution.
set_from_dataset() slices GEBCO to the model bounding box before regridding,
so a larger geographic domain means more source data to load and interpolate.
Destination resolution (nx/ny) has a secondary effect on the regrid step but
is far less important than how much of GEBCO is being read.

Parameters vary domain size in degrees at fixed 0.1° resolution, so both the
GEBCO slice and the destination grid grow together.

Requires: GEBCO_2024.nc at the path in data_config.json (gebco_path).
HPC only — skipped gracefully on machines without the file.
"""

from pathlib import Path

import psutil
import pytest

from benchmarks.common.config import get_path
from benchmarks.common.memtrack import measure_rss

GEBCO_PATH = get_path("gebco_path")
GEBCO_AVAILABLE = bool(GEBCO_PATH) and Path(GEBCO_PATH).exists()


def _has_enough_memory_for(domain_deg):
    """domain_deg=40 needs ~60 GB; require >=90 GB headroom (cgroup-aware)."""
    if domain_deg < 40:
        return True
    for cgroup_path in (
        "/sys/fs/cgroup/memory.max",  # cgroup v2
        "/sys/fs/cgroup/memory/memory.limit_in_bytes",  # cgroup v1
    ):
        try:
            val = open(cgroup_path).read().strip()
            if val != "max":
                return int(val) / 1024**3 >= 90
            break
        except FileNotFoundError:
            continue
    return psutil.virtual_memory().total / 1024**3 >= 90


@pytest.mark.heavy  # needs real GEBCO data + a meaningful regrid even at the smallest size
@pytest.mark.skipif(not GEBCO_AVAILABLE, reason="GEBCO_2024.nc not configured — GLADE only")
@pytest.mark.parametrize("domain_deg", [5, 10, 20, 40])
def test_set_from_dataset(benchmark, domain_deg, tmp_path):
    """Topo.set_from_dataset() across domain extents at fixed 0.1° resolution.

    Covers the full pipeline: GEBCO slice -> regrid_dataset_via_xesmf ->
    binary_fill_holes -> depth constraints. Cost is dominated by the size of
    the GEBCO slice (determined by domain extent), not by destination
    resolution.
    """
    if not _has_enough_memory_for(domain_deg):
        pytest.skip(f"domain_deg={domain_deg} needs ~60 GB RAM — request a high-memory node")

    from mom6_forge.grid import Grid
    from mom6_forge.topo import Topo

    grid = Grid(
        lenx=float(domain_deg),
        leny=float(domain_deg),
        resolution=0.1,
        xstart=0.0,
        ystart=0.0,
    )
    topo = Topo(grid, min_depth=10.0, git=False)
    box = {}

    def run():
        result, box["rss_mb"] = measure_rss(
            topo.set_from_dataset,
            bathymetry_path=GEBCO_PATH,
            longitude_coordinate_name="lon",
            latitude_coordinate_name="lat",
            vertical_coordinate_name="elevation",
            write_to_file=False,
            output_dir=str(tmp_path),
        )
        return result

    benchmark.pedantic(run, rounds=1, iterations=1, warmup_rounds=0)
    benchmark.extra_info["rss_mb"] = box.get("rss_mb")
