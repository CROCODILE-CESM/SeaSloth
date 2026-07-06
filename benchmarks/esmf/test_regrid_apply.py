"""
Benchmarks: ESMF regrid application via esmpy directly.

Regridder is constructed once; only the application call is timed.
Isolates the raw ESMF interpolation cost (sparse matrix multiply) without
xarray/xESMF overhead, at the same grid sizes as the xESMF suite.

CI/local: safe — all synthetic grids, no file I/O.
"""

import numpy as np
import pytest

from benchmarks.common.marks import light_or_heavy
from benchmarks.common.memtrack import PeakRSS

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


def _make_esmpy_grid(nlon, nlat, lon0=-179.0, lon1=179.0, lat0=-89.0, lat1=89.0):
    import esmpy

    grid = esmpy.Grid(
        np.array([nlon, nlat]),
        staggerloc=esmpy.StaggerLoc.CENTER,
        coord_sys=esmpy.CoordSys.SPH_DEG,
        num_peri_dims=0,
    )
    lon_arr = grid.get_coords(0)
    lat_arr = grid.get_coords(1)
    lon_vals, lat_vals = np.meshgrid(
        np.linspace(lon0, lon1, nlon),
        np.linspace(lat0, lat1, nlat),
    )
    lon_arr[...] = lon_vals.T
    lat_arr[...] = lat_vals.T
    return grid


@pytest.mark.parametrize("src_size,dst_size,ntime", APPLY_COMBOS)
@pytest.mark.parametrize("method", ["bilinear", "nearest_s2d"])
def test_apply(benchmark, src_size, dst_size, ntime, method):
    """For each time step, fills src_field.data and calls the regridder once,
    mimicking per-chunk forcing application in a CrocoDash pipeline."""
    import esmpy

    src_grid = _make_esmpy_grid(*src_size)
    dst_grid = _make_esmpy_grid(*dst_size, lon0=-100.0, lon1=100.0, lat0=-45.0, lat1=45.0)
    src_field = esmpy.Field(src_grid, name="src")
    dst_field = esmpy.Field(dst_grid, name="dst")
    src_field.data[...] = np.random.default_rng(0).uniform(0, 1, src_field.data.shape)

    method_map = {
        "bilinear": esmpy.RegridMethod.BILINEAR,
        "nearest_s2d": esmpy.RegridMethod.NEAREST_STOD,
    }
    regrid = esmpy.Regrid(
        src_field,
        dst_field,
        regrid_method=method_map[method],
        unmapped_action=esmpy.UnmappedAction.IGNORE,
    )
    peak = PeakRSS()

    def run():
        def apply_ntime():
            for _ in range(ntime):
                regrid(src_field, dst_field)

        peak.measure(apply_ntime)

    benchmark(run)
    benchmark.extra_info["rss_mb"] = peak.peak_mb

    regrid.destroy()
    dst_field.destroy()
    src_field.destroy()
    dst_grid.destroy()
    src_grid.destroy()
