"""
Benchmarks: xESMF regrid application (xe.Regridder.__call__).

Weights are pre-computed in setup() and excluded from timing.
Only the interpolation step (matrix multiply + xarray overhead) is timed.
Scales from single snapshots to 60-step monthly climatologies.

CI/local: safe — all synthetic data.
"""

import xesmf as xe

from benchmarks.common.synthetic_data import (
    make_curvilinear_grid,
    make_data_variable,
    make_locstream_grid,
    make_rect_grid,
)


class XESMFRegridApply:
    """
    xe.Regridder()(ds) application time across grid sizes and time depths.

    The regridder is constructed once in setup(); only the call is timed.
    """

    params = [
        [(300, 300), (800, 600), (1500, 700)],  # src: ~90 K, ~480 K, ~1.05 M pts
        [(150, 150), (400, 300), (700, 350)],  # dst: ~22 K, ~120 K, ~245 K pts
        [1, 12, 60],  # time steps
        ["bilinear", "nearest_s2d"],
    ]
    param_names = ["src_size", "dst_size", "ntime", "method"]
    timeout = 600

    def setup(self, src_size, dst_size, ntime, method):
        snlon, snlat = src_size
        dnlon, dnlat = dst_size
        src_grid = make_rect_grid(snlon, snlat)
        dst_grid = make_curvilinear_grid(dnlon, dnlat)
        self.src_data = make_data_variable(src_grid, ntime=ntime)
        self.regridder = xe.Regridder(
            src_grid,
            dst_grid,
            method=method,
            periodic=False,
            reuse_weights=False,
            unmapped_to_nan=True,
        )

    def time_apply(self, src_size, dst_size, ntime, method):
        self.regridder(self.src_data)

    def track_rss_mb(self, src_size, dst_size, ntime, method):
        import os

        import psutil

        proc = psutil.Process(os.getpid())
        before = proc.memory_info().rss
        self.regridder(self.src_data)
        return (proc.memory_info().rss - before) / 1024**2

    track_rss_mb.unit = "MB"


class XESMFRegridApplyLocstream:
    """
    Locstream application: the hot path in CrocoDash OBC forcing chunks.

    Source is a rectilinear GLORYS tile; destination is a 1-D OBC boundary.
    Benchmark shows throughput vs. boundary length and time depth.
    """

    params = [
        [(300, 300), (800, 600), (1500, 700)],  # src: ~90 K, ~480 K, ~1.05 M pts
        [1_000, 10_000, 100_000],  # OBC boundary points
        [1, 12, 60],
    ]
    param_names = ["src_size", "n_boundary_pts", "ntime"]
    timeout = 600

    def setup(self, src_size, n_boundary_pts, ntime):
        snlon, snlat = src_size
        src_grid = make_rect_grid(snlon, snlat)
        dst_grid = make_locstream_grid(n_boundary_pts)
        self.src_data = make_data_variable(src_grid, ntime=ntime)
        self.regridder = xe.Regridder(
            src_grid,
            dst_grid,
            method="bilinear",
            locstream_out=True,
            periodic=False,
            reuse_weights=False,
            unmapped_to_nan=True,
        )

    def time_apply(self, src_size, n_boundary_pts, ntime):
        self.regridder(self.src_data)
