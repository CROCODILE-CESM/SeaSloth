"""
Benchmarks: Grid.kdtree construction and query (mom6_forge).

Grid.kdtree builds a scipy.spatial.cKDTree from flattened tlon/tlat arrays.
This is called whenever a point lookup into the MOM6 horizontal grid is needed.

Env: mom6_forge conda env
CI/local: safe — synthetic supergrid, no file I/O.
HPC: not required.
"""

# TODO: Implement when mom6_forge Grid API is stable enough to call directly
# with a synthetic supergrid. Key function:
#   from mom6_forge.grid import Grid
#   grid = Grid(supergrid_ds)
#   _ = grid.kdtree  # triggers construction
#
# Parameters to vary:
#   nx, ny: [100, 300, 600, 1000]
#   n_queries: [100, 10_000, 100_000]
#
# See benchmarks/common/synthetic_data.make_supergrid() for the fixture.


class GridKDTreeConstruction:
    """Placeholder — implement after verifying Grid(supergrid_ds) works with synthetic data."""

    params = [[100, 300, 600]]
    param_names = ["nx"]

    def setup(self, nx):
        raise NotImplementedError("Implement: load Grid from synthetic supergrid")

    def time_kdtree_build(self, nx):
        raise NotImplementedError


class GridKDTreeQuery:
    """Placeholder — benchmark batch query performance after tree is built."""

    params = [[100, 300], [1000, 100_000]]
    param_names = ["nx", "n_queries"]

    def setup(self, nx, n_queries):
        raise NotImplementedError

    def time_kdtree_query(self, nx, n_queries):
        raise NotImplementedError
