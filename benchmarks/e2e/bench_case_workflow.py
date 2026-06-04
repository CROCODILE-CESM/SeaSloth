"""
Benchmarks: End-to-end CrocoDash Case workflow.

Times the full sequence from Case creation through CESM submission:
  Case.__init__() → create_grid() → set_from_dataset() → configure_forcings()
    → process_forcings() → build_case() → submit_case()

Requires:
  - A CESM install at ~/work/installs/
  - MOM6 input data at ~/scratch/croc_input/
  - GLORYS and GEBCO data on GLADE scratch
  - A valid PBS allocation

Env: CrocoDash conda env
CI/local: NOT safe — full CESM stack required.
HPC: run via scripts/pbs_submit.sh with a dedicated PBS allocation.
"""

# TODO: Implement. Key entry point:
#   from CrocoDash.case import Case
#   case = Case(...)
#   case.create_grid(...)
#   case.set_from_dataset(...)
#   case.configure_forcings(...)
#   case.process_forcings(...)
#
# Parameters to vary (start simple):
#   resolution: [0.1, 0.05, 0.025]   -- degrees
#   domain_size: ["small", "medium"]  -- e.g., 6°x5° vs 15°x10°


class CaseWorkflowE2E:
    """Full end-to-end case setup timing. HPC only."""

    timeout = 86400  # 24h — full workflow can be very slow

    params = [[0.1, 0.05], ["small"]]
    param_names = ["resolution", "domain_size"]

    def setup(self, resolution, domain_size):
        raise NotImplementedError(
            "Requires full CESM install and HPC data — run via scripts/pbs_submit.sh"
        )

    def time_full_case_setup(self, resolution, domain_size):
        raise NotImplementedError


class CaseGridOnly:
    """
    Benchmark only the grid + bathymetry phase (create_grid + set_from_dataset),
    excluding the forcing pipeline. Faster than full E2E but still HPC-only
    due to GEBCO dependency.
    """

    timeout = 3600

    params = [[0.1, 0.05, 0.025]]
    param_names = ["resolution"]

    def setup(self, resolution):
        raise NotImplementedError("Requires GEBCO — HPC only")

    def time_grid_and_bathy(self, resolution):
        raise NotImplementedError
