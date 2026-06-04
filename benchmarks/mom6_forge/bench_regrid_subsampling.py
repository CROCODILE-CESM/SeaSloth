"""
Benchmarks: mapping.regrid_with_subsampling() (mom6_forge).

regrid_with_subsampling() reshapes source data to (ny, nx, ny_sub, nx_sub) and
computes nanmean/nanmin/nanmax — used to compute bathymetry statistics per
destination cell from a high-resolution source.

Env: mom6_forge conda env
CI/local: safe — synthetic arrays, no file I/O.
"""

# TODO: Implement.
# from mom6_forge.mapping import regrid_with_subsampling
#
# Parameters:
#   dst_size: [(50,50), (100,100), (200,200)]
#   n_sub: [5, 10, 20, 50]   -- sub-sample points per destination cell


class RegridSubsampling:
    """Placeholder — measures regrid_with_subsampling() across sub-sample densities."""

    params = [
        [(50, 50), (100, 100), (200, 200)],
        [5, 10, 20],
    ]
    param_names = ["dst_size", "n_sub"]
    timeout = 300

    def setup(self, dst_size, n_sub):
        raise NotImplementedError

    def time_regrid_subsampling(self, dst_size, n_sub):
        raise NotImplementedError
