"""
Benchmarks: xESMF regrid application (xe.Regridder.__call__).

The regridder is pre-computed and excluded from timing — only the
interpolation step (matrix multiply + xarray overhead) is timed.
Scales from single snapshots to 60-step monthly climatologies.

CI/local: safe — all synthetic data.
"""

import pytest
import xesmf as xe

from benchmarks.common.marks import light_or_heavy
from benchmarks.common.memtrack import PeakRSS
from benchmarks.common.synthetic_data import (
    make_curvilinear_grid,
    make_data_variable,
    make_locstream_grid,
    make_rect_grid,
)

SRC_SIZES = [(300, 300), (800, 600), (1500, 700)]
DST_SIZES = [(150, 150), (400, 300), (700, 350)]
NTIMES = [1, 12, 60]

APPLY_COMBOS = [
    pytest.param(
        src, dst, ntime,
        marks=light_or_heavy(src == SRC_SIZES[0] and dst == DST_SIZES[0] and ntime == NTIMES[0]),
        id=f"src{src}-dst{dst}-t{ntime}",
    )
    for src in SRC_SIZES
    for dst in DST_SIZES
    for ntime in NTIMES
]

LOCSTREAM_COMBOS = [
    pytest.param(
        src, n, ntime,
        marks=light_or_heavy(src == SRC_SIZES[0] and n == 1_000 and ntime == NTIMES[0]),
        id=f"src{src}-n{n}-t{ntime}",
    )
    for src in SRC_SIZES
    for n in [1_000, 10_000, 100_000]
    for ntime in NTIMES
]


@pytest.mark.parametrize("src_size,dst_size,ntime", APPLY_COMBOS)
@pytest.mark.parametrize("method", ["bilinear", "nearest_s2d"])
def test_apply(benchmark, src_size, dst_size, ntime, method):
    src_grid = make_rect_grid(*src_size)
    dst_grid = make_curvilinear_grid(*dst_size)
    src_data = make_data_variable(src_grid, ntime=ntime)
    regridder = xe.Regridder(
        src_grid,
        dst_grid,
        method=method,
        periodic=False,
        reuse_weights=False,
        unmapped_to_nan=True,
    )
    peak = PeakRSS()

    def run():
        return peak.measure(regridder, src_data)

    benchmark(run)
    benchmark.extra_info["rss_mb"] = peak.peak_mb


@pytest.mark.parametrize("src_size,n_boundary_pts,ntime", LOCSTREAM_COMBOS)
def test_apply_locstream(benchmark, src_size, n_boundary_pts, ntime):
    """Locstream application: the hot path in CrocoDash OBC forcing chunks."""
    src_grid = make_rect_grid(*src_size)
    dst_grid = make_locstream_grid(n_boundary_pts)
    src_data = make_data_variable(src_grid, ntime=ntime)
    regridder = xe.Regridder(
        src_grid,
        dst_grid,
        method="bilinear",
        locstream_out=True,
        periodic=False,
        reuse_weights=False,
        unmapped_to_nan=True,
    )

    benchmark(regridder, src_data)
