"""
Benchmarks: xe.Regridder application (data interpolation).

Regridder construction (weight generation) is expensive; application is fast but
scales with grid size and number of time steps. This benchmark isolates the
application cost by pre-constructing regridders in setup().

CI/local: safe — no file I/O, all synthetic data.
"""

import xesmf as xe

from benchmarks.common.synthetic_data import (
    make_curvilinear_grid,
    make_data_variable,
    make_locstream_grid,
    make_rect_grid,
)


class RegridderApplication:
    """
    Measure regridder(ds) application time at various grid sizes and time depths.

    Setup pre-constructs the regridder — only the .apply() call is timed.
    """

    params = [
        [(100, 100), (300, 300), (600, 400)],
        [(50, 50), (200, 200), (400, 300)],
        [1, 12, 60],
        ["bilinear", "nearest_s2d"],
    ]
    param_names = ["src_size", "dst_size", "ntime", "method"]
    timeout = 300

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

    def mem_apply(self, src_size, dst_size, ntime, method):
        self.regridder(self.src_data)


class RegridderApplicationMultiVar:
    """
    Measure application time when regridding multiple variables at once.

    Regional-mom6 regrid_velocity_tracers() typically regrids temperature, salinity,
    and sometimes velocities in one call. This benchmark measures scaling with nvars.
    """

    params = [
        [(300, 300), (600, 400)],
        [(200, 200), (400, 300)],
        [1, 3, 6],
    ]
    param_names = ["src_size", "dst_size", "nvars"]
    timeout = 300

    def setup(self, src_size, dst_size, nvars):
        snlon, snlat = src_size
        dnlon, dnlat = dst_size
        src_grid = make_rect_grid(snlon, snlat)
        dst_grid = make_curvilinear_grid(dnlon, dnlat)
        self.src_data = make_data_variable(src_grid, ntime=12, nvars=nvars)
        self.regridder = xe.Regridder(
            src_grid,
            dst_grid,
            method="bilinear",
            periodic=False,
            reuse_weights=False,
            unmapped_to_nan=True,
        )

    def time_apply_multi_var(self, src_size, dst_size, nvars):
        self.regridder(self.src_data)


class LocstreamApplication:
    """
    Measure application time for the locstream_out=True OBC boundary pattern.

    This is the hot path in CrocoDash's _regrid_single_chunk() — each forcing
    chunk is regridded to a 1D boundary. Benchmark measures throughput vs.
    boundary length and number of time steps.
    """

    params = [
        [(300, 300), (600, 400)],
        [500, 2000, 5000],
        [1, 12, 60],
    ]
    param_names = ["src_size", "n_boundary_pts", "ntime"]
    timeout = 300

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

    def time_apply_locstream(self, src_size, n_boundary_pts, ntime):
        self.regridder(self.src_data)
