"""
Benchmarks: Grid._compute_MOM6_grid_metrics() (mom6_forge).

_compute_MOM6_grid_metrics() slices and assigns ~14 DataArrays from the supergrid
(shape 2ny+1 x 2nx+1). Cost scales as O(nx * ny).

Env: mom6_forge conda env
CI/local: safe — synthetic supergrid, no file I/O.
HPC: not required.
"""

# TODO: Implement. Key call:
#   from mom6_forge.grid import Grid
#   grid = Grid.__new__(Grid)
#   grid._supergrid = synthetic_supergrid
#   grid._compute_MOM6_grid_metrics()
#
# Parameters:
#   (nx, ny): [(100,100), (300,300), (600,400), (1000,1000)]


class GridMetricsComputation:
    """Placeholder — implement once Grid internal API is confirmed."""

    params = [[(100, 100), (300, 300), (600, 400)]]
    param_names = ["grid_size"]

    def setup(self, grid_size):
        raise NotImplementedError

    def time_compute_metrics(self, grid_size):
        raise NotImplementedError
