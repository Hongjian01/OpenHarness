"""G5 静态 CDS 元数据目录（DEC-G5-001）：官方/冻结 schema，不抓取门户。

单一事实来源：dataset/variables/format 复用 ``formats`` allowlist。
禁止 Selenium / Playwright / cdsapi；本模块不触网、不读凭证。
"""

from __future__ import annotations

import math
from datetime import date
from typing import Any, Mapping

from openharness.climate.errors import ClimateError, climate_error
from openharness.climate.formats import (
    ALLOWLIST_SOURCE,
    DATASET_VARIABLES,
    SUPPORTED_DATASETS,
    SUPPORTED_FORMATS,
)
from openharness.climate.models import CdsRequestInput

# 与 formats.ALLOWLIST_SOURCE 同步；检索日 2026-08-30。
CATALOG_SOURCE = ALLOWLIST_SOURCE
ERA5_SOURCE_URL = "https://cds.climate.copernicus.eu/datasets/reanalysis-era5-single-levels"
MAX_CANDIDATES = 3
GRID_RESOLUTION_DEG = 0.25
MAX_INCLUSIVE_DAYS = 366
AREA_BOUNDS = {"north": 90.0, "south": -90.0, "west": -180.0, "east": 180.0}
VARIANT_STRATEGIES = ("identity", "area_quantized", "area_outer")


def catalog_variables(dataset: str) -> frozenset[str]:
    """返回冻结 dataset 的变量集合；与 formats.DATASET_VARIABLES 同一对象。"""
    if dataset not in DATASET_VARIABLES:
        raise climate_error(
            "CLIMATE_METADATA_REJECTED",
            "dataset 不在静态 CDS 目录内",
            details={"field": "dataset", "allowed": sorted(SUPPORTED_DATASETS)},
        )
    return DATASET_VARIABLES[dataset]


def catalog_entry(dataset: str) -> dict[str, Any]:
    """冻结 schema：变量、format、area 边界、日期跨度、已登记变体。"""
    variables = catalog_variables(dataset)
    return {
        "dataset": dataset,
        "variables": sorted(variables),
        "formats": sorted(SUPPORTED_FORMATS),
        "area_bounds": dict(AREA_BOUNDS),
        "max_inclusive_days": MAX_INCLUSIVE_DAYS,
        "grid_resolution_deg": GRID_RESOLUTION_DEG,
        "variant_strategies": list(VARIANT_STRATEGIES),
        "source_url": ERA5_SOURCE_URL,
        "retrieved": "2026-08-30",
        "source": CATALOG_SOURCE,
    }


def validate_cds_request_against_catalog(
    request: CdsRequestInput | Mapping[str, Any],
) -> ClimateError | None:
    """目录校验；合法返回 None。失败码冻结为 CLIMATE_METADATA_REJECTED。"""
    if isinstance(request, CdsRequestInput):
        payload = request.model_dump(mode="json")
    elif isinstance(request, Mapping):
        payload = dict(request)
    else:
        return climate_error(
            "CLIMATE_METADATA_REJECTED",
            "cds_request 必须是对象",
            details={"field": "cds_request"},
        )

    dataset = payload.get("dataset")
    if not isinstance(dataset, str) or dataset not in SUPPORTED_DATASETS:
        return climate_error(
            "CLIMATE_METADATA_REJECTED",
            "dataset 不在静态 CDS 目录内",
            details={"field": "dataset", "allowed": sorted(SUPPORTED_DATASETS)},
        )

    fmt = payload.get("format")
    if fmt not in SUPPORTED_FORMATS:
        return climate_error(
            "CLIMATE_METADATA_REJECTED",
            "format 不在静态 CDS 目录内",
            details={"field": "format", "allowed": sorted(SUPPORTED_FORMATS)},
        )

    variables = payload.get("variables")
    if not isinstance(variables, list) or not variables:
        return climate_error(
            "CLIMATE_METADATA_REJECTED",
            "variables 必须非空且全部位于该 dataset 目录",
            details={"field": "variables", "allowed": sorted(DATASET_VARIABLES[dataset])},
        )
    allowed = DATASET_VARIABLES[dataset]
    if any(not isinstance(item, str) or item not in allowed for item in variables):
        return climate_error(
            "CLIMATE_METADATA_REJECTED",
            "variables 必须非空且全部位于该 dataset 目录",
            details={"field": "variables", "allowed": sorted(allowed)},
        )

    area_err = _reject_area(payload.get("area"))
    if area_err is not None:
        return area_err

    date_err = _reject_dates(payload.get("date_start"), payload.get("date_end"))
    if date_err is not None:
        return date_err

    return None


def expand_area_variants(area: list[float]) -> list[tuple[str, list[float]]]:
    """已登记合法 area 变体：量化到 0.25°、外扩包含盒。不含 identity。"""
    current = [float(item) for item in area]
    out: list[tuple[str, list[float]]] = []
    rounded = _snap_area(current, mode="round")
    if rounded is not None and rounded != current:
        out.append(("area_quantized", rounded))
    outer = _snap_area(current, mode="outer")
    if outer is not None and outer != current and outer != rounded:
        out.append(("area_outer", outer))
    return out[: MAX_CANDIDATES - 1]


def _reject_area(area: Any) -> ClimateError | None:
    if not isinstance(area, list) or len(area) != 4:
        return climate_error(
            "CLIMATE_METADATA_REJECTED",
            "area 必须是合法的 north/west/south/east",
            details={"field": "area"},
        )
    try:
        north, west, south, east = (float(item) for item in area)
    except (TypeError, ValueError):
        return climate_error(
            "CLIMATE_METADATA_REJECTED",
            "area 必须是合法的 north/west/south/east",
            details={"field": "area"},
        )
    if not AREA_BOUNDS["south"] <= north <= AREA_BOUNDS["north"]:
        return climate_error(
            "CLIMATE_METADATA_REJECTED",
            "area 超出静态目录纬度边界",
            details={"field": "area"},
        )
    if not AREA_BOUNDS["south"] <= south <= AREA_BOUNDS["north"]:
        return climate_error(
            "CLIMATE_METADATA_REJECTED",
            "area 超出静态目录纬度边界",
            details={"field": "area"},
        )
    if not AREA_BOUNDS["west"] <= west <= AREA_BOUNDS["east"]:
        return climate_error(
            "CLIMATE_METADATA_REJECTED",
            "area 超出静态目录经度边界",
            details={"field": "area"},
        )
    if not AREA_BOUNDS["west"] <= east <= AREA_BOUNDS["east"]:
        return climate_error(
            "CLIMATE_METADATA_REJECTED",
            "area 超出静态目录经度边界",
            details={"field": "area"},
        )
    if north <= south:
        return climate_error(
            "CLIMATE_METADATA_REJECTED",
            "area 必须是合法的 north/west/south/east",
            details={"field": "area"},
        )
    return None


def _reject_dates(date_start: Any, date_end: Any) -> ClimateError | None:
    if not isinstance(date_start, str) or not isinstance(date_end, str):
        return climate_error(
            "CLIMATE_METADATA_REJECTED",
            "日期必须是 ISO 日期且构成合法闭区间",
            details={"field": "date_start"},
        )
    try:
        start = date.fromisoformat(date_start)
        end = date.fromisoformat(date_end)
    except ValueError:
        return climate_error(
            "CLIMATE_METADATA_REJECTED",
            "日期必须是 ISO 日期且构成合法闭区间",
            details={"field": "date_start"},
        )
    if start > end:
        return climate_error(
            "CLIMATE_METADATA_REJECTED",
            "date_start 不得晚于 date_end",
            details={"field": "date_end"},
        )
    inclusive = (end - start).days + 1
    if inclusive > MAX_INCLUSIVE_DAYS:
        return climate_error(
            "CLIMATE_METADATA_REJECTED",
            "日期跨度超过静态目录上限",
            details={"field": "date_end", "reason": "date_span"},
        )
    return None


def _snap_area(area: list[float], *, mode: str) -> list[float] | None:
    north, west, south, east = area
    if mode == "round":
        north, west, south, east = (
            _round_grid(north),
            _round_grid(west),
            _round_grid(south),
            _round_grid(east),
        )
    else:
        north, west, south, east = (
            _ceil_grid(north),
            _floor_grid(west),
            _floor_grid(south),
            _ceil_grid(east),
        )
    north = min(AREA_BOUNDS["north"], max(AREA_BOUNDS["south"], north))
    south = min(AREA_BOUNDS["north"], max(AREA_BOUNDS["south"], south))
    west = min(AREA_BOUNDS["east"], max(AREA_BOUNDS["west"], west))
    east = min(AREA_BOUNDS["east"], max(AREA_BOUNDS["west"], east))
    if north <= south:
        north = min(AREA_BOUNDS["north"], south + GRID_RESOLUTION_DEG)
    if north <= south:
        return None
    return [north, west, south, east]


def _round_grid(value: float) -> float:
    return round(value / GRID_RESOLUTION_DEG) * GRID_RESOLUTION_DEG


def _floor_grid(value: float) -> float:
    n = value / GRID_RESOLUTION_DEG
    if abs(n - round(n)) < 1e-9:
        return round(n) * GRID_RESOLUTION_DEG
    return math.floor(n) * GRID_RESOLUTION_DEG


def _ceil_grid(value: float) -> float:
    n = value / GRID_RESOLUTION_DEG
    if abs(n - round(n)) < 1e-9:
        return round(n) * GRID_RESOLUTION_DEG
    return math.ceil(n) * GRID_RESOLUTION_DEG
