"""
Shared RSS memory-measurement helper for pytest-benchmark tests.

ESMF performs large C/Fortran heap allocations invisible to Python's
sys.getsizeof/tracemalloc, so memory is tracked via psutil RSS deltas instead.
"""

import os

import psutil


def measure_rss(fn, *args, **kwargs):
    """Call fn(*args, **kwargs), returning (result, rss_delta_mb)."""
    proc = psutil.Process(os.getpid())
    before = proc.memory_info().rss
    result = fn(*args, **kwargs)
    after = proc.memory_info().rss
    return result, (after - before) / 1024**2


class PeakRSS:
    """Tracks the largest RSS delta seen across repeated calls to .measure(fn).

    pytest-benchmark calls the timed function many times in the same process
    (unlike ASV's fresh-subprocess-per-benchmark model) — after the first call,
    the allocator often reuses already-freed pages, so later calls under-report
    memory use. Tracking the peak instead of the last call captures the real
    footprint regardless of call order.
    """

    def __init__(self):
        self.peak_mb = None

    def measure(self, fn, *args, **kwargs):
        result, delta = measure_rss(fn, *args, **kwargs)
        self.peak_mb = delta if self.peak_mb is None else max(self.peak_mb, delta)
        return result
