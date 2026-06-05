"""
Benchmarks: Grid._compute_MOM6_grid_metrics() (mom6_forge).

Slices and assigns ~14 DataArrays (tlon, tlat, ulon, ulat, …, tarea) from
the supergrid (shape 2ny+1 x 2nx+1). Cost scales as O(nx * ny).

No file I/O — safe on login nodes and in CI.
"""

from mom6_forge.grid import Grid


class GridMetricsComputation:
    """Time to recompute all MOM6 grid metrics from the supergrid."""

    params = [(100, 100), (300, 300), (600, 400), (1000, 1000)]
    param_names = ["grid_size"]
    timeout = 300

    def setup(self, grid_size):
        nx, ny = grid_size
        self.grid = Grid(lenx=10.0, leny=10.0, nx=nx, ny=ny, xstart=0.0, ystart=0.0)

    def time_compute_metrics(self, grid_size):
        self.grid._compute_MOM6_grid_metrics()
