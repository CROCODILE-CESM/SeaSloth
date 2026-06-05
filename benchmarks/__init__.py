import os
from pathlib import Path

# Set ESMFMKFILE to the ASV-managed conda env's esmf.mk so xesmf imports
# correctly regardless of what the parent shell's ESMFMKFILE is set to.
# This runs inside every benchmark subprocess at import time.
_repo_root = Path(__file__).parent.parent
_mk_files = sorted(_repo_root.glob("env/*/lib/esmf.mk"))
if _mk_files:
    os.environ["ESMFMKFILE"] = str(_mk_files[0])
