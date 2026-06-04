"""
Benchmarks: Topo.set_from_dataset() and mapping.regrid_dataset_via_xesmf() (mom6_forge).

set_from_dataset() calls regrid_dataset_via_xesmf() which creates an xESMF regridder
from a source bathymetry (e.g., GEBCO) to the model grid. Most expensive when
source is global GEBCO (~30M cells).

Env: mom6_forge conda env
CI/local: SMALL synthetic grids only (no GEBCO required).
HPC: full GEBCO path — requires /glade/derecho/scratch/.../GEBCO_2024.nc
"""

# TODO: Implement.
# Fast variant (CI/local):
#   - synthetic source + dest grids at (200x200) → (50x50)
#   - calls mapping.regrid_dataset_via_xesmf() directly (not Topo)
#
# Slow variant (HPC only, mark with timeout=3600):
#   - GEBCO_PATH = "/glade/derecho/scratch/manishrv/ice/croc/gebco/GEBCO_2024.nc"
#   - full Topo.set_from_dataset(bathy_path=GEBCO_PATH, ...)
#
# Key import:
#   from mom6_forge.mapping import regrid_dataset_via_xesmf
#
# Parameters:
#   src_size: [(200,200), (500,500)]  -- synthetic; larger only on HPC with GEBCO
#   dst_size: [(50,50), (100,100)]
#   method: ["bilinear", "conservative"]


class TopoRegridSynthetic:
    """Fast CI/local benchmark using synthetic source grids."""

    params = [
        [(200, 200), (500, 500)],
        [(50, 50), (100, 100)],
        ["bilinear", "conservative"],
    ]
    param_names = ["src_size", "dst_size", "method"]
    timeout = 600

    def setup(self, src_size, dst_size, method):
        raise NotImplementedError("Implement: call regrid_dataset_via_xesmf with synthetic grids")

    def time_regrid_bathy(self, src_size, dst_size, method):
        raise NotImplementedError


class TopoSetFromDatasetHPC:
    """
    Full Topo.set_from_dataset() with real GEBCO data.
    HPC only — requires GEBCO_2024.nc on GLADE scratch.
    """

    GEBCO_PATH = "/glade/derecho/scratch/manishrv/ice/croc/gebco/GEBCO_2024.nc"
    timeout = 3600

    params = [[(100, 100), (300, 300)]]
    param_names = ["dst_size"]

    def setup(self, dst_size):
        import os

        if not os.path.exists(self.GEBCO_PATH):
            raise NotImplementedError(
                f"GEBCO file not found at {self.GEBCO_PATH} — HPC only benchmark"
            )
        raise NotImplementedError("Implement: Topo.set_from_dataset() call with synthetic dst grid")

    def time_set_from_dataset(self, dst_size):
        raise NotImplementedError
