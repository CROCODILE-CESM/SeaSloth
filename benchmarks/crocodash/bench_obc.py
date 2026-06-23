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
    → must point to a valid CrocoDash case config whose raw_dataset_path
      already contains pre-downloaded GLORYS files.

  "obc_step_days_dirs": {
    "5":  "/path/to/cached_glorys_step5/",
    "15": "/path/to/cached_glorys_step15/",
    "30": "/path/to/cached_glorys_step30/"
  }
    → pre-staged raw GLORYS folders, each chunked at that step_days value.
      The benchmark swaps the raw_dataset_path for each run.

HPC only — skip gracefully on machines without the data.
"""

import shutil
import tempfile
from pathlib import Path


class OBCRegridMerge:
    """
    REGRID + MERGE phases of process_conditions() with pre-cached GLORYS data.

    step_days determines the number of raw-data chunks the regrid loop
    iterates over — smaller = more iterations, larger = fewer but bigger.
    """

    params = [[5, 15, 30]]
    param_names = ["step_days"]
    timeout = 7200

    def setup(self, step_days):
        import json

        config_path = Path(__file__).parent.parent / "data_config.json"
        with open(config_path) as f:
            cfg = json.load(f)

        obc_cfg = cfg.get("obc_config_path", "")
        step_dirs = cfg.get("obc_step_days_dirs", {})
        raw_dir = step_dirs.get(str(step_days), "")

        if not obc_cfg or not Path(obc_cfg).exists():
            raise NotImplementedError(
                "obc_config_path not set or file missing — set in data_config.json"
            )
        if not raw_dir or not Path(raw_dir).exists():
            raise NotImplementedError(
                f"obc_step_days_dirs[{step_days!r}] not set or missing — "
                "pre-stage GLORYS chunks and set in data_config.json"
            )

        self._obc_config = obc_cfg
        self._raw_dir = raw_dir
        self._tmpdir = tempfile.mkdtemp(prefix="seasloth_obc_")

    def teardown(self, step_days):
        if hasattr(self, "_tmpdir"):
            shutil.rmtree(self._tmpdir, ignore_errors=True)

    def time_regrid_and_merge(self, step_days):
        for sub in ("regridded", "output"):
            p = Path(self._tmpdir) / sub
            if p.exists():
                shutil.rmtree(p)
            p.mkdir(parents=True, exist_ok=True)

        import CrocoDash.extract_forcings.case_setup.driver as driver
        import CrocoDash.extract_forcings.regrid_dataset_piecewise as rdp
        import CrocoDash.extract_forcings.merge_piecewise_dataset as mpd
        import CrocoDash.extract_forcings.utils as utils

        config = utils.Config(self._obc_config)

        rdp.regrid_dataset_piecewise(
            self._raw_dir,
            config["basic"]["file_regex"]["raw_dataset_pattern"],
            config["basic"]["dates"]["format"],
            config["basic"]["dates"]["start"],
            config["basic"]["dates"]["end"],
            config["basic"]["paths"]["hgrid_path"],
            config["basic"]["paths"]["bathymetry_path"],
            config["basic"]["forcing"]["information"],
            Path(self._tmpdir) / "regridded",
            config["basic"]["general"]["boundary_number_conversion"],
            run_initial_condition=False,
            run_boundary_conditions=True,
            vgrid_path=config["basic"]["paths"].get("vgrid_path"),
        )

        mpd.merge_piecewise_dataset(
            Path(self._tmpdir) / "regridded",
            config["basic"]["file_regex"]["regridded_dataset_pattern"],
            config["basic"]["dates"]["format"],
            config["basic"]["dates"]["start"],
            config["basic"]["dates"]["end"],
            config["basic"]["general"]["boundary_number_conversion"],
            Path(self._tmpdir) / "output",
            run_initial_condition=False,
            run_boundary_conditions=True,
        )
