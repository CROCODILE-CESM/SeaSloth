"""
Benchmarks: Topo.tidy_dataset() (mom6_forge).

tidy_dataset() runs an iterative scipy.ndimage.binary_fill_holes loop to remove
inland lakes and narrow channels from the bathymetry mask. Convergence time
depends on grid size and the complexity of the coastline geometry.

Env: mom6_forge conda env
CI/local: synthetic binary masks — safe, no file I/O.
HPC: realistic bathymetry from set_from_dataset() output.
"""

# TODO: Implement.
# Call Topo.tidy_dataset() on a Topo object with a pre-loaded bathymetry array.
# Can generate a synthetic mask (random binary array + gaussian smoothing) to avoid
# needing real GEBCO data for the CI/fast variant.
#
# Key function: topo.tidy_dataset(fill_channels=True/False, minimum_depth=10)
# Parameters:
#   grid_size: [(100,100), (300,300), (500,500)]
#   fill_channels: [True, False]


class TopoTidyDataset:
    """Placeholder — implement with synthetic binary bathymetry mask."""

    params = [[(100, 100), (300, 300)], [True, False]]
    param_names = ["grid_size", "fill_channels"]
    timeout = 600

    def setup(self, grid_size, fill_channels):
        raise NotImplementedError

    def time_tidy_dataset(self, grid_size, fill_channels):
        raise NotImplementedError
