"""META-001 / TEST-007：静态 CDS schema 目录。禁止 Selenium、禁网、不读凭证。"""

from __future__ import annotations

import ast
import json
import socket
from pathlib import Path

import pytest

from openharness.climate.errors import ClimateError
from openharness.climate.formats import (
    ALLOWLIST_SOURCE,
    DATASET_VARIABLES,
    SUPPORTED_DATASETS,
    SUPPORTED_FORMATS,
)
from openharness.climate.models import CdsRequestInput

ROOT = Path(__file__).resolve().parents[2]
METADATA_PATH = ROOT / "src" / "openharness" / "climate" / "metadata.py"


def _legal_request(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "dataset": "reanalysis-era5-single-levels",
        "variables": ["2m_temperature"],
        "area": [40.0, 116.0, 39.0, 116.25],
        "date_start": "2025-01-01",
        "date_end": "2025-01-02",
        "format": "netcdf",
    }
    payload.update(overrides)
    return payload


@pytest.fixture(autouse=True)
def _forbid_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def _blocked(*_args: object, **_kwargs: object) -> object:
        raise RuntimeError("metadata 单元测试禁止网络")

    monkeypatch.setattr(socket, "create_connection", _blocked)
    monkeypatch.setattr(socket.socket, "connect", _blocked, raising=False)


def test_legal_request_passes_catalog() -> None:
    from openharness.climate.metadata import validate_cds_request_against_catalog

    parsed = CdsRequestInput.model_validate(_legal_request())
    assert validate_cds_request_against_catalog(parsed) is None
    assert validate_cds_request_against_catalog(_legal_request()) is None


def test_unknown_variable_is_metadata_rejected_and_redacted(tmp_path: Path) -> None:
    from openharness.climate.metadata import validate_cds_request_against_catalog

    home_leak = str(tmp_path / "Users" / "secret")
    err = validate_cds_request_against_catalog(
        _legal_request(variables=["not_a_real_era5_variable", home_leak])
    )
    assert isinstance(err, ClimateError)
    assert err.code == "CLIMATE_METADATA_REJECTED"
    assert err.retryable is False
    dumped = json.dumps(err.to_error_object(), ensure_ascii=False)
    assert "not_a_real_era5_variable" not in dumped
    assert home_leak not in dumped
    assert "C:\\" not in err.message
    assert err.details.get("field") == "variables"


def test_out_of_bounds_area_is_metadata_rejected() -> None:
    from openharness.climate.metadata import validate_cds_request_against_catalog

    err = validate_cds_request_against_catalog(_legal_request(area=[95.0, -200.0, -95.0, 200.0]))
    assert isinstance(err, ClimateError)
    assert err.code == "CLIMATE_METADATA_REJECTED"
    assert err.details.get("field") == "area"
    assert "95.0" not in json.dumps(err.to_error_object())


def test_excessive_date_span_is_metadata_rejected() -> None:
    from openharness.climate.metadata import validate_cds_request_against_catalog

    err = validate_cds_request_against_catalog(
        _legal_request(date_start="2020-01-01", date_end="2022-01-02")
    )
    assert isinstance(err, ClimateError)
    assert err.code == "CLIMATE_METADATA_REJECTED"
    assert err.details.get("field") in {"date_end", "date_start"}
    dumped = json.dumps(err.to_error_object(), ensure_ascii=False)
    assert "C:\\" not in dumped
    assert ".cdsapirc" not in dumped.lower()


def test_catalog_is_single_source_with_formats_allowlist() -> None:
    from openharness.climate.metadata import (
        CATALOG_SOURCE,
        catalog_entry,
        catalog_variables,
    )

    assert SUPPORTED_DATASETS == {"reanalysis-era5-single-levels"}
    assert catalog_variables("reanalysis-era5-single-levels") == DATASET_VARIABLES[
        "reanalysis-era5-single-levels"
    ]
    entry = catalog_entry("reanalysis-era5-single-levels")
    assert frozenset(entry["formats"]) == SUPPORTED_FORMATS
    assert CATALOG_SOURCE == ALLOWLIST_SOURCE
    assert "retrieved=2026-08-30" in CATALOG_SOURCE
    assert "cds.climate.copernicus.eu" in entry["source_url"]


def test_metadata_module_does_not_import_selenium_or_cdsapi() -> None:
    import sys

    from openharness.climate import metadata as metadata_mod

    assert metadata_mod.MAX_CANDIDATES == 3
    assert "selenium" not in sys.modules
    assert "playwright" not in sys.modules
    assert "cdsapi" not in sys.modules
    source = METADATA_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".", 1)[0])
    assert "selenium" not in imported
    assert "playwright" not in imported
    assert "cdsapi" not in imported
    assert "subprocess" not in imported
