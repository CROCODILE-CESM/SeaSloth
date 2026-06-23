"""
Benchmarks: ESMF regrid application via esmpy directly.

Regridder is constructed in setup(); only the application call is timed.
Isolates the raw ESMF interpolation cost (sparse matrix multiply) without
xarray/xESMF overhead, at the same grid sizes as the xESMF suite.

CI/local: safe — all synthetic grids, no file I/O.
"""

import numpy as np


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


class ESMFRegridApply:
    """
    esmpy.Regrid()(src, dst) application time across grid sizes and time depths.

    For each time step, fills src_field.data and calls the regridder once,
    mimicking per-chunk forcing application in a CrocoDash pipeline.
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
        import esmpy

        snlon, snlat = src_size
        dnlon, dnlat = dst_size

        self._src_grid = _make_esmpy_grid(snlon, snlat)
        self._dst_grid = _make_esmpy_grid(
            dnlon, dnlat, lon0=-100.0, lon1=100.0, lat0=-45.0, lat1=45.0
        )
        self._src_field = esmpy.Field(self._src_grid, name="src")
        self._dst_field = esmpy.Field(self._dst_grid, name="dst")
        self._src_field.data[...] = np.random.default_rng(0).uniform(
            0, 1, self._src_field.data.shape
        )

        method_map = {
            "bilinear": esmpy.RegridMethod.BILINEAR,
            "nearest_s2d": esmpy.RegridMethod.NEAREST_STOD,
        }
        self._regrid = esmpy.Regrid(
            self._src_field,
            self._dst_field,
            regrid_method=method_map[method],
            unmapped_action=esmpy.UnmappedAction.IGNORE,
        )
        self._ntime = ntime

    def teardown(self, src_size, dst_size, ntime, method):
        self._regrid.destroy()
        self._src_field.destroy()
        self._dst_field.destroy()
        self._src_grid.destroy()
        self._dst_grid.destroy()

    def time_apply(self, src_size, dst_size, ntime, method):
        for _ in range(self._ntime):
            self._regrid(self._src_field, self._dst_field)

    def track_rss_mb(self, src_size, dst_size, ntime, method):
        import os

        import psutil

        proc = psutil.Process(os.getpid())
        before = proc.memory_info().rss
        for _ in range(self._ntime):
            self._regrid(self._src_field, self._dst_field)
        return (proc.memory_info().rss - before) / 1024**2

    track_rss_mb.unit = "MB"
