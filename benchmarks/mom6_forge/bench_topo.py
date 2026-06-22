"""
Benchmarks: Topo.set_from_dataset() (mom6_forge).

Full bathymetry processing pipeline: read GEBCO, regrid to the model grid,
apply depth filters and fill algorithms.

The primary cost driver is domain extent, not destination resolution.
set_from_dataset() slices GEBCO to the model bounding box before regridding,
so a larger geographic domain means more source data to load and interpolate.
Destination resolution (nx/ny) has a secondary effect on the regrid step but
is far less important than how much of GEBCO is being read.

Parameters vary domain size in degrees at fixed 0.1° resolution, so both the
GEBCO slice and the destination grid grow together.

Requires: GEBCO_2024.nc at the path in data_config.json (gebco_path).
HPC only — skip gracefully on machines without the file.
"""

from benchmarks.common.config import get_path


class TopoSetFromDataset:
    """
    Topo.set_from_dataset() across domain extents at fixed 0.1° resolution.

    Covers the full pipeline: GEBCO slice → regrid_dataset_via_xesmf →
    binary_fill_holes → depth constraints. Cost is dominated by the size of
    the GEBCO slice (determined by domain extent), not by destination resolution.
    """

    params = [
        [5, 10, 20, 40],
    ]
    param_names = ["domain_deg"]
    timeout = 3600

    def setup(self, domain_deg):
        import tempfile

        from mom6_forge.grid import Grid
        from mom6_forge.topo import Topo

        gebco = get_path("gebco_path")
        if not gebco or not __import__("pathlib").Path(gebco).exists():
            raise NotImplementedError(f"GEBCO not found at {gebco!r} — GLADE only")

        self._grid = Grid(
            lenx=float(domain_deg),
            leny=float(domain_deg),
            resolution=0.1,
            xstart=0.0,
            ystart=0.0,
        )
        self._topo = Topo(self._grid, min_depth=10.0, git=False)
        self._gebco = gebco
        self._tmpdir = tempfile.mkdtemp(prefix="seasloth_topo_")

    def teardown(self, domain_deg):
        import shutil

        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def time_set_from_dataset(self, domain_deg):
        self._topo.set_from_dataset(
            bathymetry_path=self._gebco,
            longitude_coordinate_name="lon",
            latitude_coordinate_name="lat",
            vertical_coordinate_name="elevation",
            write_to_file=False,
            output_dir=self._tmpdir,
        )

    def track_rss_mb(self, domain_deg):
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
