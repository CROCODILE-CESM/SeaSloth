"""
Benchmarks: CrocoDash raw_data_access health checker.

Two benchmark classes:

DataAccessHealth — validates every registered access method via
  ProductRegistry.validate_function(). Returns 1.0/0.0 per method.

DataAccessLinkCheck — checks the primary documentation/download URL
  registered for each product (ProductRegistry.products[p].link) using
  an HTTP HEAD request with GET fallback. Returns 1.0/0.0 per product.

Both are parameterized dynamically — new products/methods in CrocoDash are
picked up automatically. Works anywhere CrocoDash is installed; skips
gracefully if not importable.
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
    _ALL_PRODUCTS = list(ProductRegistry.list_products())
    _CROCODASH_AVAILABLE = True
except ImportError:
    _ALL_CHECKS = [("(unavailable)", "(unavailable)")]
    _ALL_PRODUCTS = ["(unavailable)"]
    _CROCODASH_AVAILABLE = False


def _check_link(url, timeout=10):
    """HEAD then GET-stream fallback; returns True if URL is reachable."""
    import requests

    url = url.strip()
    if not url:
        return False
    try:
        r = requests.head(url, allow_redirects=True, timeout=timeout)
        if r.status_code == 200:
            return True
    except Exception:
        pass
    try:
        r = requests.get(url, stream=True, allow_redirects=True, timeout=timeout)
        next(r.iter_content(chunk_size=1), None)
        return r.status_code == 200
    except Exception:
        return False


class DataAccessHealth:
    """
    Health check for every registered CrocoDash data access method.

    Parameterized dynamically — no hardcoding required. Any product/method
    added to CrocoDash is automatically included next time benchmarks run.
    """

    params = [_ALL_CHECKS]
    param_names = ["product_method"]
    timeout = 600

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

    def time_validate(self, product_method):
        product, method = product_method
        ProductRegistry.validate_function(product, method)


class DataAccessLinkCheck:
    """
    Reachability check for each product's registered documentation/download URL.

    Uses HTTP HEAD (falling back to GET) to confirm the link is live.
    Skips products with no registered link.
    """

    params = [_ALL_PRODUCTS]
    param_names = ["product"]
    timeout = 30

    def setup(self, product):
        if not _CROCODASH_AVAILABLE:
            raise NotImplementedError(
                "CrocoDash not importable — install it or activate the CrocoDash env"
            )
        link = getattr(ProductRegistry.products.get(product), "link", None)
        if not link or not link.strip():
            raise NotImplementedError(f"No link registered for product '{product}'")
        self._link = link

    def track_link_ok(self, product):
        return 1.0 if _check_link(self._link) else 0.0

    track_link_ok.unit = "pass"

    def time_link_check(self, product):
        _check_link(self._link)
