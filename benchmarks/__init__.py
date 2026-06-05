import json
import os
import sys
from pathlib import Path

# Set ESMFMKFILE to the ASV-managed conda env's esmf.mk so xesmf imports
# correctly regardless of what the parent shell's ESMFMKFILE is set to.
# This runs inside every benchmark subprocess at import time.
_repo_root = Path(__file__).parent.parent
_mk_files = sorted(_repo_root.glob("env/*/lib/esmf.mk"))
if _mk_files:
    os.environ["ESMFMKFILE"] = str(_mk_files[0])

# Add local package source roots so mom6_forge and CrocoDash are importable
# inside the ASV conda env (they are not conda-forge packages).
_config_path = Path(__file__).parent / "data_config.json"
if _config_path.exists():
    with open(_config_path) as _f:
        _config = json.load(_f)
    for _key in ("mom6_forge_src", "crocodash_src"):
        _path = _config.get(_key, "")
        if _path and _path not in sys.path:
            sys.path.insert(0, _path)
