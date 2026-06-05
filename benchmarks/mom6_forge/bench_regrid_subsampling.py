"""
Benchmarks: mapping.regrid_with_subsampling() (mom6_forge).

Reshapes source data to (ny, nx, ny_sub, nx_sub) and regrids — used to
compute per-cell bathymetry statistics from a high-resolution source.
Cost scales as O(ny * nx * n_sub**2).

No file I/O — safe on login nodes and in CI.
"""

from benchmarks.common.synthetic_data import make_data_variable, make_rect_grid


class RegridSubsampling:
    """regrid_with_subsampling() across destination sizes and sub-sample densities."""

    params = [
        [(50, 50), (100, 100), (200, 200)],
        [5, 10, 20],
    ]
    param_names = ["dst_size", "n_sub"]
    timeout = 600

    def setup(self, dst_size, n_sub):
        from mom6_forge.grid import Grid
        from mom6_forge.mapping import regrid_with_subsampling

        dst_nx, dst_ny = dst_size
        # Source: fine 1D rect grid covering the same domain
        src_nx, src_ny = dst_nx * n_sub, dst_ny * n_sub
        src = make_rect_grid(src_nx, src_ny, lon0=0.0, lon1=10.0, lat0=0.0, lat1=10.0)
        self._src = make_data_variable(src, ntime=1)

        # Destination q-point corners come from a mom6_forge Grid
        grid = Grid(lenx=10.0, leny=10.0, nx=dst_nx, ny=dst_ny, xstart=0.0, ystart=0.0)
        self._qlon = grid.qlon.values  # shape (dst_ny+1, dst_nx+1)
        self._qlat = grid.qlat.values
        self._n_sub = n_sub
        self._regrid = regrid_with_subsampling

    def time_regrid_subsampling(self, dst_size, n_sub):
        self._regrid(
            input_dataset=self._src,
            qlon=self._qlon,
            qlat=self._qlat,
            nx_sub=self._n_sub,
            ny_sub=self._n_sub,
        )
