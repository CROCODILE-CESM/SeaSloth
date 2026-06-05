"""
Benchmarks: Grid.kdtree construction and nearest-neighbour query (mom6_forge).

Grid.kdtree is a lazy property that builds a scipy.spatial.cKDTree from the
flattened t-grid lat/lon arrays. Cost scales as O(nx * ny * log(nx * ny)).

No file I/O — safe on login nodes and in CI.
"""

import numpy as np


class GridKDTreeBuild:
    """Time and memory cost of building the kdtree from scratch."""

    params = [100, 300, 600, 1000]
    param_names = ["nx"]
    timeout = 300

    def setup(self, nx):
        from mom6_forge.grid import Grid

        self.grid = Grid(lenx=10.0, leny=10.0, nx=nx, ny=nx, xstart=0.0, ystart=0.0)
        _ = self.grid.kdtree  # warm up once so the property path is exercised

    def time_kdtree_build(self, nx):
        self.grid._kdtree = None
        _ = self.grid.kdtree

    def track_rss_mb(self, nx):
        import os

        import psutil

        proc = psutil.Process(os.getpid())
        self.grid._kdtree = None
        before = proc.memory_info().rss
        _ = self.grid.kdtree
        return (proc.memory_info().rss - before) / 1024**2


GridKDTreeBuild.track_rss_mb.unit = "MB"


class GridKDTreeQuery:
    """Batch nearest-neighbour query time after the tree is already built."""

    params = [[100, 300, 600], [1_000, 100_000]]
    param_names = ["nx", "n_queries"]
    timeout = 300

    def setup(self, nx, n_queries):
        from mom6_forge.grid import Grid

        self.grid = Grid(lenx=10.0, leny=10.0, nx=nx, ny=nx, xstart=0.0, ystart=0.0)
        _ = self.grid.kdtree  # build once
        rng = np.random.default_rng(42)
        self.query_points = np.column_stack(
            (
                rng.uniform(0.0, 10.0, n_queries),  # lat
                rng.uniform(0.0, 10.0, n_queries),  # lon
            )
        )

    def time_kdtree_query(self, nx, n_queries):
        self.grid.kdtree.query(self.query_points)
