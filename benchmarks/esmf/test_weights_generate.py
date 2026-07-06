"""
Benchmarks: ESMF weight generation via esmpy directly.

Uses the esmpy Grid/Field/Regrid objects without the xarray/xESMF layer.
Isolates the raw ESMF weight-generation cost at the same grid sizes as the
xESMF suite so the two can be compared directly.

CI/local: safe — all synthetic grids, no file I/O.
"""

import numpy as np
import pytest

from benchmarks.common.marks import light_or_heavy
from benchmarks.common.memtrack import PeakRSS

SRC_SIZES = [(300, 300), (800, 600), (1500, 700)]
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


def _make_esmpy_grid(nlon, nlat, lon0=-179.0, lon1=179.0, lat0=-89.0, lat1=89.0):
    """Return an esmpy.Grid with evenly spaced lon/lat coordinates."""
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


@pytest.mark.parametrize("src_size,dst_size", WEIGHTS_COMBOS)
@pytest.mark.parametrize("method", ["bilinear", "nearest_s2d"])
def test_generate_weights(benchmark, src_size, dst_size, method):
    """esmpy.Regrid() construction time = raw ESMF weight generation."""
    import esmpy

    src_grid = _make_esmpy_grid(*src_size)
    dst_grid = _make_esmpy_grid(*dst_size, lon0=-100.0, lon1=100.0, lat0=-45.0, lat1=45.0)
    src_field = esmpy.Field(src_grid, name="src")
    dst_field = esmpy.Field(dst_grid, name="dst")
    method_map = {
        "bilinear": esmpy.RegridMethod.BILINEAR,
        "nearest_s2d": esmpy.RegridMethod.NEAREST_STOD,
    }
    peak = PeakRSS()

    def run():
        def build():
            regrid = esmpy.Regrid(
                src_field,
                dst_field,
                regrid_method=method_map[method],
                unmapped_action=esmpy.UnmappedAction.IGNORE,
            )
            regrid.destroy()

        peak.measure(build)

    benchmark(run)
    benchmark.extra_info["rss_mb"] = peak.peak_mb

    dst_field.destroy()
    src_field.destroy()
    dst_grid.destroy()
    src_grid.destroy()
