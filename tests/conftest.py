"""Pytest configuration and shared fixtures."""

import pytest

_TINGBOK_URL = "https://tingbok.plann.no"
_tingbok_reachable: bool | None = None


def _check_tingbok() -> bool:
    global _tingbok_reachable
    if _tingbok_reachable is not None:
        return _tingbok_reachable
    try:
        import niquests

        r = niquests.get(f"{_TINGBOK_URL}/api/vocabulary", timeout=3.0)
        _tingbok_reachable = r.status_code < 500
    except Exception:
        _tingbok_reachable = False
    return _tingbok_reachable


def pytest_collection_modifyitems(items: list) -> None:
    """Skip integration-marked tests when tingbok is unreachable."""
    integration_items = [i for i in items if i.get_closest_marker("integration")]
    if not integration_items:
        return
    if _check_tingbok():
        return
    skip = pytest.mark.skip(reason=f"tingbok not reachable ({_TINGBOK_URL})")
    for item in integration_items:
        item.add_marker(skip)
