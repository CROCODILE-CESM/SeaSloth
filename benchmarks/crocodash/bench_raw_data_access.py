"""
Benchmarks: CrocoDash raw_data_access health checker.

Imports all registered dataset modules and validates every access method
via ProductRegistry.validate_function(). New datasets/methods are picked up
automatically when they are added to CrocoDash — nothing to update here.

Returns 1.0 (accessible/working) or 0.0 (not accessible) per method.

Works anywhere CrocoDash is installed. Skips gracefully if not importable.
"""

try:
    from CrocoDash.raw_data_access.registry import ProductRegistry
    from CrocoDash.raw_data_access.datasets import load_all_datasets

    load_all_datasets()

    _ALL_CHECKS = [
        (product, method)
        for product in ProductRegistry.list_products()
        for method in ProductRegistry.list_access_methods(product)
    ]
    _CROCODASH_AVAILABLE = True
except ImportError:
    _ALL_CHECKS = [("(unavailable)", "(unavailable)")]
    _CROCODASH_AVAILABLE = False


class DataAccessHealth:
    """
    Health check for every registered CrocoDash data access method.

    Parameterized dynamically — no hardcoding required. Any product/method
    added to CrocoDash is automatically included next time benchmarks run.
    """

    params = [_ALL_CHECKS]
    param_names = ["product_method"]
    timeout = 120

    def setup(self, _product_method):
        if not _CROCODASH_AVAILABLE:
            raise NotImplementedError(
                "CrocoDash not importable — install it or activate the CrocoDash env"
            )

    def track_accessible(self, product_method):
        product, method = product_method
        try:
            ProductRegistry.validate_function(product, method)
            return 1.0
        except Exception:
            return 0.0

    track_accessible.unit = "pass"
