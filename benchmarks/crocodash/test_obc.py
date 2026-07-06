"""
Benchmarks: CrocoDash OBC forcing pipeline — REGRID + MERGE phases only.

process_conditions() orchestrates three phases:
  1. GET    — download raw GLORYS chunks  (skipped here)
  2. REGRID — regrid each chunk to MOM6 boundary segments
  3. MERGE  — concatenate into final boundary forcing files

This benchmark skips GET and times only REGRID + MERGE, using pre-cached
GLORYS files already on disk. This isolates the computational cost from
network/storage variability.

step_days controls the chunking of the raw dataset — smaller values mean more
but smaller files (more regrid iterations); larger values mean fewer, bigger
files. The total date range is held constant so total data volume is fixed.

Required setup in data_config.json:
  "obc_config_path": "/path/to/CrocoDash/case/config.yaml"
    -> must point to a valid CrocoDash case config whose raw_dataset_path
       already contains pre-downloaded GLORYS files.

  "obc_step_days_dirs": {
    "5":  "/path/to/cached_glorys_step5/",
    "15": "/path/to/cached_glorys_step15/",
    "30": "/path/to/cached_glorys_step30/"
  }
    -> pre-staged raw GLORYS folders, each chunked at that step_days value.
       The benchmark swaps the raw_dataset_path for each run.

HPC only — skipped gracefully on machines without the data.
"""

from pathlib import Path

import pytest

from benchmarks.common.config import get_path

OBC_CONFIG_PATH = get_path("obc_config_path")
OBC_STEP_DAYS_DIRS = {}
try:
    import json

    _cfg_path = Path(__file__).parent.parent / "data_config.json"
    OBC_STEP_DAYS_DIRS = json.loads(_cfg_path.read_text()).get("obc_step_days_dirs", {})
except FileNotFoundError:
    pass


def _raw_dir_for(step_days):
    return OBC_STEP_DAYS_DIRS.get(str(step_days), "")


def _obc_available(step_days):
    if not OBC_CONFIG_PATH or not Path(OBC_CONFIG_PATH).exists():
        return False
    raw_dir = _raw_dir_for(step_days)
    return bool(raw_dir) and Path(raw_dir).exists()


@pytest.mark.heavy  # needs pre-staged GLORYS data + a real regrid+merge pass at every size
@pytest.mark.parametrize("step_days", [5, 15, 30])
def test_regrid_and_merge(benchmark, step_days, tmp_path):
    """REGRID + MERGE phases of process_conditions() with pre-cached GLORYS data.

    step_days determines the number of raw-data chunks the regrid loop
    iterates over — smaller = more iterations, larger = fewer but bigger.
    """
    if not _obc_available(step_days):
        pytest.skip(
            f"obc_config_path/obc_step_days_dirs[{step_days}] not configured — GLADE only"
        )

    raw_dir = _raw_dir_for(step_days)

    def run():
        import CrocoDash.extract_forcings.case_setup.driver as driver  # noqa: F401
        import CrocoDash.extract_forcings.merge_piecewise_dataset as mpd
        import CrocoDash.extract_forcings.regrid_dataset_piecewise as rdp
        import CrocoDash.extract_forcings.utils as utils

        regridded_dir = tmp_path / "regridded"
        output_dir = tmp_path / "output"
        regridded_dir.mkdir(exist_ok=True)
        output_dir.mkdir(exist_ok=True)

        config = utils.Config(OBC_CONFIG_PATH)

        rdp.regrid_dataset_piecewise(
            raw_dir,
            config["basic"]["file_regex"]["raw_dataset_pattern"],
            config["basic"]["dates"]["format"],
            config["basic"]["dates"]["start"],
            config["basic"]["dates"]["end"],
            config["basic"]["paths"]["hgrid_path"],
            config["basic"]["paths"]["bathymetry_path"],
            config["basic"]["forcing"]["information"],
            regridded_dir,
            config["basic"]["general"]["boundary_number_conversion"],
            run_initial_condition=False,
            run_boundary_conditions=True,
            vgrid_path=config["basic"]["paths"].get("vgrid_path"),
        )

        mpd.merge_piecewise_dataset(
            regridded_dir,
            config["basic"]["file_regex"]["regridded_dataset_pattern"],
            config["basic"]["dates"]["format"],
            config["basic"]["dates"]["start"],
            config["basic"]["dates"]["end"],
            config["basic"]["general"]["boundary_number_conversion"],
            output_dir,
            run_initial_condition=False,
            run_boundary_conditions=True,
        )

    benchmark.pedantic(run, rounds=1, iterations=1, warmup_rounds=0)
