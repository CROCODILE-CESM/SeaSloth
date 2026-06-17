"""
Benchmarks: xESMF (ESMF) weight generation via xe.Regridder construction.

Weight generation is the expensive ESMF step — parallel ESMF search finds
source-to-destination cell mappings. Grids scale from ~90 K to ~1 M source
points so throughput at oceanographic resolutions is visible.

CI/local: safe — all synthetic grids, no file I/O.
"""

import xesmf as xe

from benchmarks.common.synthetic_data import make_curvilinear_grid, make_rect_grid


class XESMFWeightsGenerate:
    """
    xe.Regridder() construction time = ESMF weight generation.

    Source grids are rectilinear (lon/lat boxes); destinations are curvilinear
    (matching regional-mom6 output grids). Sizes span ~90 K → ~1 M source pts.
    """

    params = [
        [(300, 300), (800, 600), (1500, 700)],   # src: ~90 K, ~480 K, ~1.05 M pts
        [(150, 150), (400, 300), (700, 350)],     # dst: ~22 K, ~120 K, ~245 K pts
        ["bilinear", "conservative"],
    ]
    param_names = ["src_size", "dst_size", "method"]
    timeout = 1800

    def setup(self, src_size, dst_size, method):
        snlon, snlat = src_size
        dnlon, dnlat = dst_size
        self.src = make_rect_grid(snlon, snlat)
        self.dst = make_curvilinear_grid(dnlon, dnlat)

    def time_generate_weights(self, src_size, dst_size, method):
        xe.Regridder(
            self.src,
            self.dst,
            method=method,
            periodic=False,
            reuse_weights=False,
            unmapped_to_nan=True,
        )

    def track_rss_mb(self, src_size, dst_size, method):
        import os

        import psutil

        proc = psutil.Process(os.getpid())
        before = proc.memory_info().rss
        xe.Regridder(
            self.src,
            self.dst,
            method=method,
            periodic=False,
            reuse_weights=False,
            unmapped_to_nan=True,
        )
        return (proc.memory_info().rss - before) / 1024**2

    track_rss_mb.unit = "MB"


class XESMFWeightsGenerateLocstream:
    """
    xe.Regridder() construction with locstream_out=True.

    Matches the CrocoDash OBC boundary pattern: 1-D destination points along
    a model open boundary. Sizes span ~90 K source pts to ~1 M.
    """

    params = [
        [(300, 300), (800, 600), (1500, 700)],   # src: ~90 K, ~480 K, ~1.05 M pts
        [1_000, 10_000, 100_000],                 # OBC boundary points
        ["bilinear", "nearest_s2d"],
    ]
    param_names = ["src_size", "n_boundary_pts", "method"]
    timeout = 1800

    def setup(self, src_size, n_boundary_pts, method):
        from benchmarks.common.synthetic_data import make_locstream_grid

        snlon, snlat = src_size
        self.src = make_rect_grid(snlon, snlat)
        self.dst = make_locstream_grid(n_boundary_pts)

    def time_generate_weights(self, src_size, n_boundary_pts, method):
        xe.Regridder(
            self.src,
            self.dst,
            method=method,
            locstream_out=True,
            periodic=False,
            reuse_weights=False,
            unmapped_to_nan=True,
        )

    def track_rss_mb(self, src_size, n_boundary_pts, method):
        import os

        import psutil

        proc = psutil.Process(os.getpid())
        before = proc.memory_info().rss
        xe.Regridder(
            self.src,
            self.dst,
            method=method,
            locstream_out=True,
            periodic=False,
            reuse_weights=False,
            unmapped_to_nan=True,
        )
        return (proc.memory_info().rss - before) / 1024**2

    track_rss_mb.unit = "MB"
