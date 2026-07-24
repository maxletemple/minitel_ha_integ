"""Shared fixtures for Minitel Interface tests."""

import pytest

pytest_plugins = "pytest_homeassistant_custom_component"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Make custom_components discoverable, per pytest-homeassistant-custom-component."""
    yield
