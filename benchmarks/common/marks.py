"""
Shared helper for the light/heavy pytest markers.

"light" tags the smallest parameter combination in a sweep — a fast smoke
test that exercises the code path without paying for the full-size run.
Everything else is "heavy". Run just the light ones with `-m light`.
"""

import pytest


def light_or_heavy(is_light):
    return pytest.mark.light if is_light else pytest.mark.heavy
