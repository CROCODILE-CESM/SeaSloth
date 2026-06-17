"""
Benchmarks: Topo.set_from_dataset() (mom6_forge).

Full bathymetry processing pipeline: read GEBCO, regrid to the model grid,
apply depth filters and fill algorithms. Cost scales with destination grid size.

Requires: GEBCO_2024.nc at the path in data_config.json (gebco_path).
HPC only — skip gracefully on machines without the file.
"""

from benchmarks.common.config import get_path


class TopoSetFromDataset:
    """
    Topo.set_from_dataset() across regional grid sizes.

    Covers the full pipeline: regrid_dataset_via_xesmf → binary_fill_holes →
    depth constraints → write. Cost is dominated by the ESMF weight generation
    and the scipy morphological fill.
    """

    params = [
        [(100, 100), (300, 300), (600, 400), (1000, 600)],
    ]
    param_names = ["dst_size"]
    timeout = 3600

    def setup(self, dst_size):
        import tempfile

        from mom6_forge.grid import Grid
        from mom6_forge.topo import Topo

        gebco = get_path("gebco_path")
        if not gebco or not __import__("pathlib").Path(gebco).exists():
            raise NotImplementedError(f"GEBCO not found at {gebco!r} — GLADE only")

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

    def track_rss_mb(self, dst_size):
        import os

        import psutil

        proc = psutil.Process(os.getpid())
        before = proc.memory_info().rss
        self._topo.set_from_dataset(
            bathymetry_path=self._gebco,
            longitude_coordinate_name="lon",
            latitude_coordinate_name="lat",
            vertical_coordinate_name="elevation",
            write_to_file=False,
            output_dir=self._tmpdir,
        )
        return (proc.memory_info().rss - before) / 1024**2

    track_rss_mb.unit = "MB"
