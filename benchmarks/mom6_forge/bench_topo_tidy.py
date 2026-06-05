"""
Benchmarks: Topo.tidy_dataset() (mom6_forge).

tidy_dataset() runs scipy.ndimage binary_fill_holes to remove inland lakes
and optionally fill narrow channels. Convergence time scales with grid size
and coastline complexity.

Synthetic bathymetry with ~20% land (depth ≤ 0) — no file I/O.
"""

import numpy as np
import xarray as xr

from mom6_forge.grid import Grid
from mom6_forge.topo import Topo


class TopoTidyDataset:
    """tidy_dataset() cost across grid sizes and fill_channels flag."""

    params = [
        [(100, 100), (300, 300), (500, 500)],
        [False, True],
    ]
    param_names = ["grid_size", "fill_channels"]
    timeout = 600

    def setup(self, grid_size, fill_channels):
        nx, ny = grid_size
        grid = Grid(lenx=10.0, leny=10.0, nx=nx, ny=ny, xstart=0.0, ystart=0.0)
        self._topo = Topo(grid, min_depth=10.0, git=False)
        # ~20% cells are land (depth ≤ 0) to produce a realistic coastline
        rng = np.random.default_rng(42)
        depth = rng.uniform(-200.0, 800.0, (ny, nx)).astype(np.float32)
        self._bathy = xr.Dataset(
            {"depth": (["ny", "nx"], depth)},
            coords={
                "lon": (["ny", "nx"], grid.tlon.values),
                "lat": (["ny", "nx"], grid.tlat.values),
            },
        )

    def time_tidy_dataset(self, grid_size, fill_channels):
        self._topo.tidy_dataset(
            fill_channels=fill_channels,
            bathymetry=self._bathy,
        )
