"""
Benchmarks: mapping.regrid_dataset_via_xesmf() and Topo.set_from_dataset() (mom6_forge).

Two classes:
  RegridDatasetSynthetic — fast, no data files needed; exercises the
      xESMF regridder creation + application path directly.
  TopoSetFromDataset — full pipeline with real GEBCO; path from data_config.json.

No writes to disk (write_to_file=False for the synthetic variant).
"""

import numpy as np
import xarray as xr

from benchmarks.common.config import get_path
from benchmarks.common.synthetic_data import make_curvilinear_grid, make_rect_grid
from mom6_forge.mapping import regrid_dataset_via_xesmf


class RegridDatasetSynthetic:
    """regrid_dataset_via_xesmf() with in-memory synthetic source and destination."""

    params = [
        [(200, 200), (500, 500)],
        [(50, 50), (100, 100)],
        ["bilinear", "conservative"],
    ]
    param_names = ["src_size", "dst_size", "method"]
    timeout = 600

    def setup(self, src_size, dst_size, method):
        src_nlon, src_nlat = src_size
        dst_nlon, dst_nlat = dst_size
        src = make_rect_grid(src_nlon, src_nlat)
        rng = np.random.default_rng(42)
        src["elevation"] = xr.DataArray(
            rng.uniform(-200.0, 5000.0, (src_nlat, src_nlon)).astype(np.float32),
            dims=["lat", "lon"],
        )
        self.src = src
        self.dst = make_curvilinear_grid(dst_nlon, dst_nlat)
        self.method = method

    def time_regrid(self, src_size, dst_size, method):
        regrid_dataset_via_xesmf(
            input_dataset=self.src,
            output_dataset=self.dst,
            regridding_method=self.method,
            write_to_file=False,
        )


class TopoSetFromDataset:
    """Full Topo.set_from_dataset() pipeline with real GEBCO bathymetry.

    Path is read from benchmarks/data_config.json (gebco_path).
    Skipped as n/a if the file is not present.
    """

    params = [(100, 100), (300, 300)]
    param_names = ["dst_size"]
    timeout = 3600

    def setup(self, dst_size):
        import tempfile

        from mom6_forge.grid import Grid
        from mom6_forge.topo import Topo

        gebco = get_path("gebco_path")
        if not gebco or not __import__("pathlib").Path(gebco).exists():
            raise NotImplementedError(f"GEBCO file not found at {gebco!r}")

        nx, ny = dst_size
        self._grid = Grid(lenx=10.0, leny=10.0, nx=nx, ny=ny, xstart=0.0, ystart=0.0)
        self._topo = Topo(self._grid, min_depth=10.0, git=False)
        self._gebco = gebco
        self._tmpdir = tempfile.mkdtemp(prefix="crocoscope_topo_")

    def teardown(self, dst_size):
        import shutil

        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def time_set_from_dataset(self, dst_size):
        self._topo.set_from_dataset(
            bathymetry_path=self._gebco,
            longitude_coordinate_name="lon",
            latitude_coordinate_name="lat",
            vertical_coordinate_name="elevation",
            write_to_file=False,
            output_dir=self._tmpdir,
        )
