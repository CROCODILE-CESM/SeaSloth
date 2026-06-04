"""
Benchmarks: CrocoDash process_obc_conditions() — OBC forcing pipeline.

process_obc_conditions() is the main 3-phase forcing pipeline:
  1. GET  — parallel Dask download of GLORYS chunks from RDA
  2. REGRID — sequential regrid of each chunk to MOM6 boundary segments
  3. MERGE — concatenate segments into final boundary forcing files

This benchmark requires:
  - Access to GLORYS data on GLADE/RDA
  - A valid CrocoDash config JSON pointing to real or cached forcing data
  - A Dask cluster (local or PBS)

Env: CrocoDash conda env
CI/local: NOT safe — requires HPC data access. Skip on CI.
HPC: run via scripts/pbs_submit.sh
"""

# TODO: Implement once a suitable small cached GLORYS dataset is available for
# benchmarking. Options:
#   A. Use a pre-cached small regional GLORYS subset (e.g., 1 month, 6° x 6° box)
#   B. Mock the GET phase and only benchmark REGRID + MERGE
#
# Entry point:
#   from CrocoDash.extract_forcings.obc import process_obc_conditions
#   process_obc_conditions(config_path=..., client=dask_client, preview=False)
#
# Parameters to vary:
#   n_workers: [1, 4, 8]         -- Dask local cluster size
#   step_days: [5, 15, 30]       -- chunk size for GET phase
#   arakawa_grid: ["A", "B", "C"]


class OBCPipeline:
    """
    Full process_obc_conditions() timing.
    HPC only — requires GLORYS data access.
    """

    timeout = 7200

    params = [[1, 4], [5, 15]]
    param_names = ["n_workers", "step_days"]

    def setup(self, n_workers, step_days):
        raise NotImplementedError(
            "Requires HPC GLORYS data access — run via scripts/pbs_submit.sh"
        )

    def time_process_obc(self, n_workers, step_days):
        raise NotImplementedError


class OBCRegridOnly:
    """
    Benchmark only the REGRID phase of process_obc_conditions(), using cached
    pre-downloaded forcing data. Eliminates network variability.
    HPC — needs cached GLORYS files on GLADE scratch.
    """

    timeout = 3600

    params = [[(100, 100), (300, 300)], ["bilinear", "nearest_s2d"]]
    param_names = ["hgrid_size", "regrid_method"]

    def setup(self, hgrid_size, regrid_method):
        raise NotImplementedError("Implement: load cached forcing, call regrid step only")

    def time_regrid_phase(self, hgrid_size, regrid_method):
        raise NotImplementedError
