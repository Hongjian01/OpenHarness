"""Day 11 注册 climate_integration；默认 CI 禁网，不读取凭证。"""

from __future__ import annotations

import pytest

from openharness.climate.formats import (
    climate_integration_credentials_present,
    climate_integration_enabled,
    climate_integration_skip_reason,
)


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """未显式启用且凭证齐全时才跑真实 CDS；skip reason 不含路径或 token。"""
    if climate_integration_enabled() and climate_integration_credentials_present():
        return
    skip = pytest.mark.skip(reason=climate_integration_skip_reason())
    for item in items:
        if "climate_integration" in item.keywords:
            item.add_marker(skip)
