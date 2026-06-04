"""
Benchmarks: xe.Regridder construction (weight computation).

Weight generation is the expensive ESMF step — it runs a parallel ESMF search
to find source-to-destination cell mappings. This benchmark isolates that cost
across grid sizes and regridding methods.

CI/local: safe — all grids are synthetic, no file I/O, no HPC data.
"""

import xesmf as xe

from benchmarks.common.synthetic_data import make_curvilinear_grid, make_rect_grid


class RegridderCreation:
    """
    Measure xe.Regridder() construction time (= ESMF weight generation).

    Parameters
    ----------
    src_size : (nlon, nlat) of source rectilinear grid
    dst_size : (nlon, nlat) of destination curvilinear grid
    method   : xESMF regridding method
    """

    params = [
        [(100, 100), (300, 300), (600, 400)],
        [(50, 50), (200, 200), (400, 300)],
        ["bilinear", "nearest_s2d", "conservative"],
    ]
    param_names = ["src_size", "dst_size", "method"]
    timeout = 600

    def setup(self, src_size, dst_size, method):
        snlon, snlat = src_size
        dnlon, dnlat = dst_size
        self.src = make_rect_grid(snlon, snlat)
        self.dst = make_curvilinear_grid(dnlon, dnlat)

    def time_create_regridder(self, src_size, dst_size, method):
        xe.Regridder(
            self.src,
            self.dst,
            method=method,
            periodic=False,
            reuse_weights=False,
            unmapped_to_nan=True,
        )

    def mem_create_regridder(self, src_size, dst_size, method):
        # Return the regridder so ASV can measure its object size (weight matrix).
        return xe.Regridder(
            self.src,
            self.dst,
            method=method,
            periodic=False,
            reuse_weights=False,
            unmapped_to_nan=True,
        )


class RegridderCreationLocstream:
    """
    Measure xe.Regridder() construction with locstream_out=True.

    This matches the CrocoDash OBC boundary regridding pattern where the
    destination is a 1D set of points along a model boundary (not a 2D grid).
    """

    params = [
        [(100, 100), (300, 300), (600, 400)],
        [500, 2000, 5000],
        ["bilinear", "nearest_s2d"],
    ]
    param_names = ["src_size", "n_boundary_pts", "method"]
    timeout = 600

    def setup(self, src_size, n_boundary_pts, method):
        from benchmarks.common.synthetic_data import make_locstream_grid

        snlon, snlat = src_size
        self.src = make_rect_grid(snlon, snlat)
        self.dst = make_locstream_grid(n_boundary_pts)

    def time_create_locstream_regridder(self, src_size, n_boundary_pts, method):
        xe.Regridder(
            self.src,
            self.dst,
            method=method,
            locstream_out=True,
            periodic=False,
            reuse_weights=False,
            unmapped_to_nan=True,
        )

    def mem_create_locstream_regridder(self, src_size, n_boundary_pts, method):
        return xe.Regridder(
            self.src,
            self.dst,
            method=method,
            locstream_out=True,
            periodic=False,
            reuse_weights=False,
            unmapped_to_nan=True,
        )


class RegridderWeightReuse:
    """
    Compare regridder construction with and without weight reuse.

    reuse_weights=True skips ESMF weight generation if a weight file already exists.
    This benchmark measures the difference — critical for understanding multi-chunk
    forcing pipelines where the same grid is regridded repeatedly.
    """

    params = [
        [(300, 300), (600, 400)],
        [(200, 200), (400, 300)],
        [True, False],
    ]
    param_names = ["src_size", "dst_size", "reuse_weights"]
    timeout = 600

    def setup(self, src_size, dst_size, reuse_weights):
        import tempfile
        import os

        snlon, snlat = src_size
        dnlon, dnlat = dst_size
        self.src = make_rect_grid(snlon, snlat)
        self.dst = make_curvilinear_grid(dnlon, dnlat)

        self._tmpdir = tempfile.mkdtemp()
        self._weight_file = os.path.join(
            self._tmpdir, f"weights_{snlon}x{snlat}_to_{dnlon}x{dnlat}.nc"
        )

        if reuse_weights:
            # Pre-generate the weight file so reuse actually reuses
            xe.Regridder(
                self.src,
                self.dst,
                method="bilinear",
                periodic=False,
                reuse_weights=False,
                filename=self._weight_file,
                unmapped_to_nan=True,
            )

    def teardown(self, src_size, dst_size, reuse_weights):
        import shutil

        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def time_create_with_reuse_setting(self, src_size, dst_size, reuse_weights):
        xe.Regridder(
            self.src,
            self.dst,
            method="bilinear",
            periodic=False,
            reuse_weights=reuse_weights,
            filename=self._weight_file,
            unmapped_to_nan=True,
        )
