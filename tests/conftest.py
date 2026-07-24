"""Shared fixtures for Minitel Interface tests.

This repo ships with content_in_root (hacs.json): the integration lives at
the repo root, not under custom_components/<domain>/, so it can be cloned
directly as custom_components/minitel_interface. HA's loader still expects
that layout though, so we create a local, gitignored symlink
custom_components/minitel_interface -> repo root before collecting tests.
"""

from pathlib import Path

import pytest

pytest_plugins = "pytest_homeassistant_custom_component"

_REPO_ROOT = Path(__file__).parent.parent
_SYMLINK = _REPO_ROOT / "custom_components" / "minitel_interface"


def pytest_configure(config):
    _SYMLINK.parent.mkdir(exist_ok=True)
    if not _SYMLINK.exists():
        _SYMLINK.symlink_to("..", target_is_directory=True)


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Make custom_components discoverable, per pytest-homeassistant-custom-component."""
    yield
