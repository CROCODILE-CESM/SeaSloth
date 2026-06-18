import importlib
import sys


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
        # Evict the module so the import is not cached
        for key in list(sys.modules.keys()):
            if key == module or key.startswith(module + "."):
                del sys.modules[key]

    def time_import(self, module):
        importlib.import_module(module)
