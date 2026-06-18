import importlib
import sys

_EVICT_PREFIXES = ("CrocoDash", "mom6_forge")


class CrocoDashImports:
    params = [
        [
            "CrocoDash.case",
            "mom6_forge.grid",
            "mom6_forge.topo",
            "mom6_forge.vgrid",
        ]
    ]
    param_names = ["module"]
    timeout = 60

    def setup(self, module):
        pass

    def time_import(self, module):
        # Evict before every call — ASV calls this many times in a loop,
        # so without this every call after the first hits sys.modules cache.
        for key in list(sys.modules.keys()):
            if any(key == p or key.startswith(p + ".") for p in _EVICT_PREFIXES):
                del sys.modules[key]
        importlib.import_module(module)
