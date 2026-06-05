"""
Benchmarks: CrocoDash raw_data_access GLORYS download throughput.

Two sources:
  GLORYSRDAThroughput       — GLADE campaign storage; no credentials needed
  GLORYSCopernicusThroughput — Copernicus Marine API; needs credentials

Credentials for Copernicus: run `copernicusmarine login` once on the target
machine (stores credentials in ~/.copernicusmarine/), or set env vars:
  COPERNICUSMARINE_SERVICE_USERNAME / COPERNICUSMARINE_SERVICE_PASSWORD

track_mb_per_sec: end-to-end MB/s (glob → open → sel → to_netcdf).

Both benchmarks download a fixed small region (3 days, 5° × 5°) so results
are comparable across runs. Results vary with storage/network load, so run
several times and look at the distribution.
"""

import os
import tempfile
import time
from pathlib import Path

from benchmarks.common.config import get_path

# Import GLORYS at module level with a graceful fallback so the file still
# loads in environments where CrocoDash or copernicusmarine is absent.
try:
    from CrocoDash.raw_data_access.datasets.glorys import GLORYS as _GLORYS

    _GLORYS_AVAILABLE = True
except Exception:
    _GLORYS_AVAILABLE = False

_DATES = ["2010-01-01", "2010-01-03"]
_LAT_MIN, _LAT_MAX = 10.0, 15.0
_LON_MIN, _LON_MAX = -30.0, -25.0


class GLORYSRDAThroughput:
    """End-to-end GLORYS throughput from GLADE RDA campaign storage.

    Measures: glob matching + xr.open_mfdataset + spatial sel + to_netcdf.
    No network; bottleneck is campaign storage I/O bandwidth.
    """

    timeout = 600

    def setup(self):
        if not _GLORYS_AVAILABLE:
            raise NotImplementedError("CrocoDash not importable — check data_config.json")
        rda = get_path("glorys_rda_path")
        if not rda or not Path(rda).exists():
            raise NotImplementedError(f"RDA path not found: {rda!r} — GLADE only")
        self._tmpdir = tempfile.mkdtemp(prefix="crocoscope_rda_")

    def teardown(self):
        import shutil

        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def track_mb_per_sec(self):
        t0 = time.perf_counter()
        path = _GLORYS.get_glorys_data_from_rda(
            dates=_DATES,
            lat_min=_LAT_MIN,
            lat_max=_LAT_MAX,
            lon_min=_LON_MIN,
            lon_max=_LON_MAX,
            output_folder=self._tmpdir,
            output_filename="bench_rda.nc",
        )
        elapsed = time.perf_counter() - t0
        size_mb = os.path.getsize(str(path)) / 1024**2
        return size_mb / max(elapsed, 1e-6)


GLORYSRDAThroughput.track_mb_per_sec.unit = "MB/s"


class GLORYSCopernicusThroughput:
    """GLORYS download throughput via Copernicus Marine Service API.

    Requires credentials on the machine where benchmarks run:
      copernicusmarine login
    or env vars COPERNICUSMARINE_SERVICE_USERNAME / _PASSWORD.

    Skipped as n/a if copernicusmarine is not installed or not authenticated.
    """

    timeout = 1800

    def setup(self):
        if not _GLORYS_AVAILABLE:
            raise NotImplementedError("CrocoDash not importable — check data_config.json")
        try:
            import copernicusmarine  # noqa: F401
        except ImportError:
            raise NotImplementedError("copernicusmarine not installed in this env")
        self._tmpdir = tempfile.mkdtemp(prefix="crocoscope_copernicus_")

    def teardown(self):
        import shutil

        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def track_mb_per_sec(self):
        t0 = time.perf_counter()
        path = _GLORYS.get_glorys_data_from_cds_api(
            dates=_DATES,
            lat_min=_LAT_MIN,
            lat_max=_LAT_MAX,
            lon_min=_LON_MIN,
            lon_max=_LON_MAX,
            output_folder=self._tmpdir,
            output_filename="bench_copernicus.nc",
        )
        elapsed = time.perf_counter() - t0
        size_mb = os.path.getsize(str(path)) / 1024**2
        return size_mb / max(elapsed, 1e-6)


GLORYSCopernicusThroughput.track_mb_per_sec.unit = "MB/s"
