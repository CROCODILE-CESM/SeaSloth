"""
Benchmarks: mom6_forge gen_rof_maps() — runoff-to-ocean mapping.

gen_rof_maps() produces (1) a nearest-neighbour mapping file and (2) a smoothed
nearest-neighbour mapping file between a river-routing (ROF) ESMF mesh and an
ocean (OCN) ESMF mesh. The ROF mesh is held constant (JRA55); the OCN (destination)
mesh varies across pairs to show how cost scales with destination grid size.

Cost scales with OCN mesh size (number of destination elements) and, for the
smoothed map, with rmax/fold parameters.

Requires: pre-existing ESMF mesh NetCDF files listed under "mesh_pairs" in
data_config.json. Skipped gracefully on machines without the files or insufficient
memory.

data_config.json entry:
  "mesh_pairs": [
    {
      "label": "coarse_dst",
      "rof_mesh": "/path/to/jra55_rof_mesh.nc",   # constant across pairs
      "ocn_mesh": "/path/to/ocn_coarse.nc",
      "rmax": 100.0,
      "fold": 25.0,
      "min_memory_gb": 8.0                         # optional; skip if below this
    },
    ...
  ]
"""

import tempfile
import shutil
from pathlib import Path

from benchmarks.common.config import get_path


def _load_mesh_pairs():
    """Return list of mesh pair dicts from data_config.json, or empty list."""
    import json

    config_path = Path(__file__).parent.parent / "data_config.json"
    if not config_path.exists():
        return []
    with open(config_path) as f:
        cfg = json.load(f)
    return cfg.get("mesh_pairs", [])


def _check_memory(pair_dict):
    """Raise NotImplementedError if the job's memory limit is below min_memory_gb."""
    min_gb = pair_dict.get("min_memory_gb")
    if not min_gb:
        return
    import psutil

    # Prefer cgroup limit (what PBS actually enforces) over system total.
    cgroup_limit_gb = None
    for cgroup_path in (
        "/sys/fs/cgroup/memory.max",
        "/sys/fs/cgroup/memory/memory.limit_in_bytes",
    ):
        try:
            val = open(cgroup_path).read().strip()
            if val != "max":
                cgroup_limit_gb = int(val) / 1024**3
            break
        except FileNotFoundError:
            continue
    limit_gb = (
        cgroup_limit_gb if cgroup_limit_gb else psutil.virtual_memory().total / 1024**3
    )
    if limit_gb < min_gb:
        raise NotImplementedError(
            f"mesh pair '{pair_dict['label']}' needs ~{min_gb:.0f} GB; "
            f"memory limit is {limit_gb:.0f} GB — request a larger node"
        )


_MESH_PAIRS = _load_mesh_pairs()
_MESH_LABELS = (
    [p["label"] for p in _MESH_PAIRS] if _MESH_PAIRS else ["(no mesh pairs configured)"]
)


class RunoffMappingNearestNeighbour:
    """
    gen_rof_maps() — nearest-neighbour mapping only (rmax=None).

    Uses esmpy/xesmf under the hood to build an ESMF mapping file from the ROF
    mesh to the OCN mesh. Cost scales with OCN mesh size (number of destination
    elements).
    """

    params = [_MESH_LABELS]
    param_names = ["mesh_pair"]
    timeout = 3600

    def setup(self, mesh_pair):
        pairs = {p["label"]: p for p in _load_mesh_pairs()}
        if mesh_pair not in pairs:
            raise NotImplementedError(
                f"Mesh pair {mesh_pair!r} not in data_config.json — add 'mesh_pairs' entries"
            )
        p = pairs[mesh_pair]
        rof = Path(p["rof_mesh"])
        ocn = Path(p["ocn_mesh"])
        if not rof.exists():
            raise NotImplementedError(f"ROF mesh not found: {rof}")
        if not ocn.exists():
            raise NotImplementedError(f"OCN mesh not found: {ocn}")
        _check_memory(p)
        self._rof = rof
        self._ocn = ocn
        self._tmpdir = Path(tempfile.mkdtemp(prefix="seasloth_rof_"))

    def teardown(self, mesh_pair):
        if hasattr(self, "_tmpdir"):
            shutil.rmtree(self._tmpdir, ignore_errors=True)

    def time_gen_rof_maps_nn(self, mesh_pair):
        from mom6_forge.mapping import gen_rof_maps

        gen_rof_maps(
            rof_mesh_path=self._rof,
            ocn_mesh_path=self._ocn,
            output_dir=self._tmpdir,
            mapping_file_prefix=f"bench_{mesh_pair}_nn",
            rmax=None,
            fold=None,
        )


class RunoffMappingSmoothed:
    """
    gen_rof_maps() — nearest-neighbour + smoothed mapping (rmax/fold set).

    The smoothed step builds a scipy sparse matrix of distance-weighted
    neighbours and applies it to the NN weights. Cost scales with OCN mesh
    size and the smoothing radius (rmax).
    """

    params = [_MESH_LABELS]
    param_names = ["mesh_pair"]
    timeout = 7200

    def setup(self, mesh_pair):
        pairs = {p["label"]: p for p in _load_mesh_pairs()}
        if mesh_pair not in pairs:
            raise NotImplementedError(
                f"Mesh pair {mesh_pair!r} not in data_config.json — add 'mesh_pairs' entries"
            )
        p = pairs[mesh_pair]
        rof = Path(p["rof_mesh"])
        ocn = Path(p["ocn_mesh"])
        if not rof.exists():
            raise NotImplementedError(f"ROF mesh not found: {rof}")
        if not ocn.exists():
            raise NotImplementedError(f"OCN mesh not found: {ocn}")
        _check_memory(p)
        self._rof = rof
        self._ocn = ocn
        self._rmax = p.get("rmax", 100.0)
        self._fold = p.get("fold", 25.0)
        self._tmpdir = Path(tempfile.mkdtemp(prefix="seasloth_rof_sm_"))

    def teardown(self, mesh_pair):
        if hasattr(self, "_tmpdir"):
            shutil.rmtree(self._tmpdir, ignore_errors=True)

    def time_gen_rof_maps_smoothed(self, mesh_pair):
        from mom6_forge.mapping import gen_rof_maps

        gen_rof_maps(
            rof_mesh_path=self._rof,
            ocn_mesh_path=self._ocn,
            output_dir=self._tmpdir,
            mapping_file_prefix=f"bench_{mesh_pair}_sm",
            rmax=self._rmax,
            fold=self._fold,
        )
