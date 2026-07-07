"""
Benchmarks: CrocoDash OBC forcing pipeline — REGRID + MERGE phases only.

process_obc_conditions() runs GET -> REGRID -> MERGE for every configured
boundary. GET is idempotent (skips a boundary/chunk whose output file already
exists), so pre-staging correctly-named raw files turns GET into a handful of
Path.exists() checks — letting this benchmark isolate REGRID+MERGE compute
cost from GET's network/storage variability, while still exercising the real,
public process_obc_conditions() entry point rather than reaching into private
phase functions (which have already changed shape once).

regrid_step (config: basic.general.regrid_step) controls how many days of
data are regridded per xESMF call — smaller means more, smaller regrid calls;
larger means fewer, bigger ones. The GET chunking and date range are held
fixed across the sweep so total data volume is fixed.

Required setup in data_config.json:
  "obc_hgrid_path" / "obc_bathymetry_path" / "obc_vgrid_path"
      -> grid + bathymetry files from an existing CrocoDash case (read-only
         for this benchmark; vgrid is optional).
  "obc_raw_data_dir"
      -> a directory of pre-downloaded GLORYS OBC files, one per boundary,
         named "{boundary}_unprocessed.{start}_{end}.nc" (ISO dates) spanning
         the full obc_dates_start..obc_dates_end range in a single GET chunk.
  "obc_dates_start" / "obc_dates_end"
      -> the date range those raw files cover (any pandas-parseable format).

HPC only — skipped gracefully on machines without the data.
"""

import json
from pathlib import Path

import pandas as pd
import pytest

from benchmarks.common.config import get_path

HGRID_PATH = get_path("obc_hgrid_path")
BATHYMETRY_PATH = get_path("obc_bathymetry_path")
VGRID_PATH = get_path("obc_vgrid_path")
RAW_DATA_DIR = get_path("obc_raw_data_dir")
DATES_START = get_path("obc_dates_start")
DATES_END = get_path("obc_dates_end")

BOUNDARY_NUMBER_CONVERSION = {"south": 1, "north": 2, "west": 3, "east": 4}

# Full field set required by regional_mom6's variable-mapping validation.
FORCING_INFORMATION = {
    "product_name": "glorys",
    "time_var_name": "time",
    "time_units": "days",
    "boundary_fill_method": "regional_mom6",
    "tracer_x_coord": "longitude",
    "tracer_y_coord": "latitude",
    "u_var_name": "uo",
    "v_var_name": "vo",
    "u_y_coord": "latitude",
    "u_x_coord": "longitude",
    "v_x_coord": "longitude",
    "v_y_coord": "latitude",
    "u_lat_coord": "latitude",
    "u_lon_coord": "longitude",
    "v_lat_coord": "latitude",
    "v_lon_coord": "longitude",
    "tracer_lat_coord": "latitude",
    "tracer_lon_coord": "longitude",
    "eta_var_name": "zos",
    "depth_coord": "depth",
    "tracer_var_names": {"temp": "thetao", "salt": "so"},
}


def _obc_available():
    return bool(
        HGRID_PATH and BATHYMETRY_PATH and RAW_DATA_DIR and DATES_START and DATES_END
    ) and Path(RAW_DATA_DIR).exists()


def _stage_raw_files(tmp_path):
    """Symlink pre-downloaded raw files into a scratch raw dir under the
    ISO-dated filename GET's idempotency check expects, turning GET into a
    no-op without touching the network."""
    raw_dir = tmp_path / "raw_data"
    raw_dir.mkdir()
    start = pd.to_datetime(DATES_START).strftime("%Y-%m-%d")
    end = pd.to_datetime(DATES_END).strftime("%Y-%m-%d")
    for boundary in BOUNDARY_NUMBER_CONVERSION:
        src = Path(RAW_DATA_DIR) / f"{boundary}_unprocessed.{start}_{end}.nc"
        if not src.exists():
            pytest.skip(f"missing pre-staged raw file: {src}")
        (raw_dir / src.name).symlink_to(src)
    return raw_dir


def _write_config(tmp_path, raw_dir, regrid_step):
    regridded_dir = tmp_path / "regridded"
    output_dir = tmp_path / "output"
    regridded_dir.mkdir()
    output_dir.mkdir()

    paths = {
        "raw_dataset_path": str(raw_dir),
        "hgrid_path": HGRID_PATH,
        "bathymetry_path": BATHYMETRY_PATH,
        "regridded_dataset_path": str(regridded_dir),
        "output_path": str(output_dir),
        "input_dataset_path": str(tmp_path),
    }
    if VGRID_PATH:
        paths["vgrid_path"] = VGRID_PATH

    config = {
        "basic": {
            "paths": paths,
            "dates": {"start": DATES_START, "end": DATES_END},
            "forcing": {
                "product_name": "GLORYS",
                "function_name": "get_glorys_data_from_rda",
                "information": FORCING_INFORMATION,
            },
            "general": {
                "boundary_number_conversion": BOUNDARY_NUMBER_CONVERSION,
                "regrid_step": regrid_step,
            },
        }
    }
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps(config))
    return config_path


@pytest.mark.heavy  # needs pre-staged GLORYS data + a real regrid+merge pass at every size
@pytest.mark.parametrize("step_days", [5, 15, 30])
def test_regrid_and_merge(benchmark, step_days, tmp_path):
    """REGRID + MERGE phases of process_obc_conditions(), GET skipped via
    pre-staged raw files. step_days sets the regrid chunk size — smaller
    means more, smaller xESMF calls for the same total date range."""
    if not _obc_available():
        pytest.skip("obc_* paths not configured in data_config.json — GLADE only")

    raw_dir = _stage_raw_files(tmp_path)
    config_path = _write_config(tmp_path, raw_dir, step_days)

    def run():
        from CrocoDash.extract_forcings.obc import process_obc_conditions

        process_obc_conditions(str(config_path), preview=False)

    benchmark.pedantic(run, rounds=1, iterations=1, warmup_rounds=0)
