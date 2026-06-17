"""
Benchmarks: ESMF weight generation via esmpy directly.

Uses the esmpy Grid/Field/Regrid objects without the xarray/xESMF layer.
Isolates the raw ESMF weight-generation cost at the same grid sizes as the
xESMF suite so the two can be compared directly.

CI/local: safe — all synthetic grids, no file I/O.
"""

import numpy as np


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


class ESMFWeightsGenerate:
    """
    esmpy.Regrid() construction time = raw ESMF weight generation.

    Source and destination are regular lat-lon grids defined directly via
    esmpy.Grid — no xarray, no xESMF overhead. Sizes mirror the xESMF suite
    so the two can be compared.
    """

    params = [
        [(300, 300), (800, 600), (1500, 700)],   # src: ~90 K, ~480 K, ~1.05 M pts
        [(150, 150), (400, 300), (700, 350)],     # dst: ~22 K, ~120 K, ~245 K pts
        ["bilinear", "nearest_s2d"],
    ]
    param_names = ["src_size", "dst_size", "method"]
    timeout = 1800

    def setup(self, src_size, dst_size, method):
        import esmpy

        snlon, snlat = src_size
        dnlon, dnlat = dst_size
        self._src_grid = _make_esmpy_grid(snlon, snlat)
        self._dst_grid = _make_esmpy_grid(
            dnlon, dnlat, lon0=-100.0, lon1=100.0, lat0=-45.0, lat1=45.0
        )
        self._src_field = esmpy.Field(self._src_grid, name="src")
        self._dst_field = esmpy.Field(self._dst_grid, name="dst")

        self._method_map = {
            "bilinear": esmpy.RegridMethod.BILINEAR,
            "nearest_s2d": esmpy.RegridMethod.NEAREST_STOD,
        }

    def teardown(self, src_size, dst_size, method):
        self._src_field.destroy()
        self._dst_field.destroy()
        self._src_grid.destroy()
        self._dst_grid.destroy()

    def time_generate_weights(self, src_size, dst_size, method):
        import esmpy

        regrid = esmpy.Regrid(
            self._src_field,
            self._dst_field,
            regrid_method=self._method_map[method],
            unmapped_action=esmpy.UnmappedAction.IGNORE,
        )
        regrid.destroy()

    def track_rss_mb(self, src_size, dst_size, method):
        import os

        import esmpy
        import psutil

        proc = psutil.Process(os.getpid())
        before = proc.memory_info().rss
        regrid = esmpy.Regrid(
            self._src_field,
            self._dst_field,
            regrid_method=self._method_map[method],
            unmapped_action=esmpy.UnmappedAction.IGNORE,
        )
        rss_delta = (proc.memory_info().rss - before) / 1024**2
        regrid.destroy()
        return rss_delta

    track_rss_mb.unit = "MB"
