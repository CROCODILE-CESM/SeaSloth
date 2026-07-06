"""
Benchmarks: xESMF (ESMF) weight generation via xe.Regridder construction.

Weight generation is the expensive ESMF step — parallel ESMF search finds
source-to-destination cell mappings. Grids scale from ~90 K to ~1 M source
points so throughput at oceanographic resolutions is visible.

CI/local: safe — all synthetic grids, no file I/O.
"""

import pytest
import xesmf as xe

from benchmarks.common.marks import light_or_heavy
from benchmarks.common.memtrack import PeakRSS
from benchmarks.common.synthetic_data import (
    make_curvilinear_grid,
    make_locstream_grid,
    make_rect_grid,
)

# src: ~90 K, ~480 K, ~1.05 M pts
SRC_SIZES = [(300, 300), (800, 600), (1500, 700)]
# dst: ~22 K, ~120 K, ~245 K pts
DST_SIZES = [(150, 150), (400, 300), (700, 350)]

WEIGHTS_COMBOS = [
    pytest.param(
        src, dst,
        marks=light_or_heavy(src == SRC_SIZES[0] and dst == DST_SIZES[0]),
        id=f"src{src}-dst{dst}",
    )
    for src in SRC_SIZES
    for dst in DST_SIZES
]

LOCSTREAM_COMBOS = [
    pytest.param(
        src, n,
        marks=light_or_heavy(src == SRC_SIZES[0] and n == 1_000),
        id=f"src{src}-n{n}",
    )
    for src in SRC_SIZES
    for n in [1_000, 10_000, 100_000]
]


@pytest.mark.parametrize("src_size,dst_size", WEIGHTS_COMBOS)
@pytest.mark.parametrize("method", ["bilinear", "conservative"])
def test_generate_weights(benchmark, src_size, dst_size, method):
    """xe.Regridder() construction time = ESMF weight generation.

    Source grids are rectilinear (lon/lat boxes); destinations are curvilinear
    (matching regional-mom6 output grids).
    """
    src = make_rect_grid(*src_size)
    dst = make_curvilinear_grid(*dst_size)
    peak = PeakRSS()

    def run():
        return peak.measure(
            xe.Regridder,
            src,
            dst,
            method=method,
            periodic=False,
            reuse_weights=False,
            unmapped_to_nan=True,
        )

    benchmark(run)
    benchmark.extra_info["rss_mb"] = peak.peak_mb


@pytest.mark.parametrize("src_size,n_boundary_pts", LOCSTREAM_COMBOS)
@pytest.mark.parametrize("method", ["bilinear", "nearest_s2d"])
def test_generate_weights_locstream(benchmark, src_size, n_boundary_pts, method):
    """xe.Regridder() construction with locstream_out=True.

    Matches the CrocoDash OBC boundary pattern: 1-D destination points along
    a model open boundary.
    """
    src = make_rect_grid(*src_size)
    dst = make_locstream_grid(n_boundary_pts)
    peak = PeakRSS()

    def run():
        return peak.measure(
            xe.Regridder,
            src,
            dst,
            method=method,
            locstream_out=True,
            periodic=False,
            reuse_weights=False,
            unmapped_to_nan=True,
        )

    benchmark(run)
    benchmark.extra_info["rss_mb"] = peak.peak_mb
