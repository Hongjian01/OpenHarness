"""G5 产物规则校验（VAL-001）：只读，不执行代码，不修改源数据。"""

from __future__ import annotations

import csv
import json
import math
import re
from pathlib import Path
from typing import Any, NoReturn

from openharness.climate.errors import climate_error, redact_secrets
from openharness.climate.formats import format_from_extension, validate_published_artifact
from openharness.climate.models import RunContext
from openharness.climate.repository import ContextRepository

_SECRET_HINT = re.compile(
    r"(?i)(?:api[_-]?key|token|password|secret|authorization)\s*[:=]\s*\S+|sk-[A-Za-z0-9_-]{8,}|cds-token-\S+"
)
_REQUIRED_HEADINGS = ("## Inspect", "## Plot", "## Summary")
_MAX_CSV_SAMPLE_ROWS = 64
_MAX_REPORT_CHARS = 8000


def score_report_markdown(text: str, *, workspace: Path | None = None) -> int:
    """本地规则分 0～10；不是 Bench-85，也不是联网 LLM judge。"""
    score = 0
    if text.lstrip().startswith("# "):
        score += 2
    score += sum(1 for heading in _REQUIRED_HEADINGS if heading in text)
    if "](.climate/" in text:
        score += 2
    if len(text) >= 80:
        score += 2
    if workspace is not None and str(workspace) in text:
        score -= 3
    if _SECRET_HINT.search(text):
        score -= 4
    if "bench-85" in text.lower() and "不是" not in text and "非" not in text:
        score -= 2
    return max(0, min(10, score))


def validate_run_artifacts(workspace: Path, *, run_id: str | None = None) -> dict[str, Any]:
    """对当前 run 产物做规则校验；失败抛出 CLIMATE_VALIDATION_FAILED。"""
    repo = ContextRepository(workspace)
    if repo.has_pending_active_run_transaction():
        raise climate_error(
            "CLIMATE_RECOVERY_REQUIRED",
            "存在未完成的 active-run 事务，请先执行受权限控制的恢复 mutation",
            details={"reason": "pending_wal"},
            workspace=workspace,
        )
    resolved = run_id
    if resolved is None:
        index = repo.load_index()
        if index.active_run_id is None:
            raise climate_error(
                "CLIMATE_RUN_NOT_FOUND",
                "没有 active run",
                workspace=workspace,
            )
        resolved = index.active_run_id
    context = repo.load_run(resolved)
    return _validate_context(workspace, context)


def _validate_context(workspace: Path, context: RunContext) -> dict[str, Any]:
    checks: list[str] = []
    dataset = _latest_kind(context, "dataset")
    profile = _latest_kind(context, "profile")
    plot = _latest_kind(context, "plot")
    report = _latest_kind(context, "report")

    if dataset is None:
        _fail(workspace, "missing_dataset", "缺少 dataset 产物")
    dataset_path = _existing_file(workspace, dataset.path, check="dataset")
    if dataset_path.stat().st_size <= 0:
        _fail(workspace, "empty_dataset", "dataset 产物为空")
    claimed = format_from_extension(dataset_path)
    if claimed in {"netcdf", "grib"}:
        validate_published_artifact(dataset_path, claimed)
        checks.append("dataset_magic")
    else:
        checks.append("dataset_nonempty")

    if profile is None:
        _fail(workspace, "missing_profile", "缺少 inspect profile")
    profile_path = _existing_file(workspace, profile.path, check="profile")
    profile_data = _load_profile_json(profile_path, workspace)
    _require_profile_fields(profile_data, workspace)
    checks.append("profile_fields")

    if plot is None:
        _fail(workspace, "missing_plot", "缺少 plot 产物")
    plot_path = _existing_file(workspace, plot.path, check="plot")
    if plot_path.stat().st_size <= 0:
        _fail(workspace, "empty_plot", "plot 产物为空")
    checks.append("plot_exists")

    if report is None:
        _fail(workspace, "missing_report", "缺少 report 产物")
    report_path = _existing_file(workspace, report.path, check="report")
    report_text = _read_utf8_markdown(report_path, workspace)
    _require_report_rules(report_text, workspace)
    checks.append("report_markdown")

    _require_declared_values(dataset_path, profile_data, workspace)
    checks.append("declared_values")

    score = score_report_markdown(report_text, workspace=workspace)
    return {
        "ok": True,
        "checks": checks,
        "score": score,
        "report_is_bench85": False,
    }


def _latest_kind(context: RunContext, kind: str) -> Any:
    found = [item for item in context.artifacts if item.kind == kind]
    return found[-1] if found else None


def _existing_file(workspace: Path, relative: str, *, check: str) -> Path:
    path = workspace / relative
    if not path.is_file():
        _fail(workspace, check, f"{check} 产物不存在")
    return path


def _load_profile_json(path: Path, workspace: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        _fail(workspace, "profile", "inspect profile 不是合法 JSON")
    if not isinstance(payload, dict):
        _fail(workspace, "profile", "inspect profile 必须是对象")
    return payload


def _require_profile_fields(profile: dict[str, Any], workspace: Path) -> None:
    has_variables = isinstance(profile.get("variables"), list) and bool(profile["variables"])
    has_columns = isinstance(profile.get("columns"), list) and bool(profile["columns"])
    if not has_variables and not has_columns:
        _fail(workspace, "profile", "inspect profile 缺少 variables 或 columns")
    has_dims = isinstance(profile.get("dimensions"), dict) and bool(profile["dimensions"])
    has_rows = isinstance(profile.get("row_count"), int)
    if not has_dims and not has_rows:
        _fail(workspace, "profile", "inspect profile 缺少 dims 或 row_count")
    if not _has_bounded_stats(profile):
        _fail(workspace, "profile", "inspect profile 缺少有界统计")


def _has_bounded_stats(profile: dict[str, Any]) -> bool:
    stats = profile.get("statistics")
    if isinstance(stats, dict):
        for item in stats.values():
            if isinstance(item, dict) and {"min", "max", "mean"} <= item.keys():
                return True
    columns = profile.get("columns")
    if isinstance(columns, list):
        for column in columns:
            if isinstance(column, dict) and {"min", "max", "mean"} <= column.keys():
                return True
    return False


def _read_utf8_markdown(path: Path, workspace: Path) -> str:
    try:
        raw = path.read_bytes()
        text = raw.decode("utf-8")
    except (OSError, UnicodeDecodeError):
        _fail(workspace, "report", "report 必须是 UTF-8 Markdown")
    if not text.strip():
        _fail(workspace, "report", "report 不得为空")
    return text.replace("\r\n", "\n")


def _require_report_rules(text: str, workspace: Path) -> None:
    if not text.lstrip().startswith("# "):
        _fail(workspace, "report", "report 必须含 Markdown 标题")
    missing = [heading for heading in _REQUIRED_HEADINGS if heading not in text]
    if missing:
        _fail(workspace, "report", "report 缺少约定章节")
    if "](.climate/" not in text:
        _fail(workspace, "report", "report 必须使用相对路径引用产物")
    abs_ws = str(workspace)
    if abs_ws in text or str(workspace.resolve()) in text:
        _fail(workspace, "report", "report 不得包含绝对路径")
    if _SECRET_HINT.search(text):
        _fail(workspace, "report", "report 含有疑似密钥")


def _require_declared_values(
    dataset_path: Path, profile: dict[str, Any], workspace: Path
) -> None:
    claimed = format_from_extension(dataset_path)
    if claimed in {"netcdf", "grib"}:
        variables = profile.get("variables")
        if not isinstance(variables, list) or not variables:
            _fail(workspace, "variables", "科学数据未声明变量")
        stats = profile.get("statistics")
        if not isinstance(stats, dict):
            _fail(workspace, "statistics", "科学数据缺少有界统计")
        for name in variables:
            if not isinstance(name, str):
                continue
            item = stats.get(name)
            if not isinstance(item, dict):
                _fail(workspace, "statistics", "声明变量缺少统计")
            count = item.get("count")
            if isinstance(count, int) and count <= 0:
                _fail(workspace, "statistics", "声明变量数值全缺失")
        return
    if dataset_path.name.lower().endswith(".csv"):
        _require_csv_columns(dataset_path, profile, workspace)


def _require_csv_columns(
    dataset_path: Path, profile: dict[str, Any], workspace: Path
) -> None:
    columns = profile.get("columns")
    if not isinstance(columns, list) or not columns:
        _fail(workspace, "columns", "CSV profile 缺少 columns")
    declared = [
        str(item.get("name"))
        for item in columns
        if isinstance(item, dict) and item.get("name")
    ]
    try:
        with dataset_path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.reader(handle)
            header = next(reader)
            if any(name not in header for name in declared):
                _fail(workspace, "columns", "CSV 缺少声明列")
            numeric_idx = [
                header.index(str(item["name"]))
                for item in columns
                if isinstance(item, dict)
                and item.get("dtype") in {"int", "float"}
                and item.get("name") in header
            ]
            seen_numeric = {index: False for index in numeric_idx}
            for row_i, row in enumerate(reader):
                if row_i >= _MAX_CSV_SAMPLE_ROWS:
                    break
                for index in numeric_idx:
                    if index >= len(row):
                        continue
                    try:
                        value = float(row[index])
                    except ValueError:
                        continue
                    if not math.isnan(value):
                        seen_numeric[index] = True
            if numeric_idx and not any(seen_numeric.values()):
                _fail(workspace, "columns", "CSV 数值列全为缺失")
    except OSError:
        _fail(workspace, "dataset", "无法读取 dataset")


def _fail(workspace: Path, check: str, message: str) -> NoReturn:
    raise climate_error(
        "CLIMATE_VALIDATION_FAILED",
        redact_secrets(message, workspace=workspace),
        details={"check": check, "reason": check},
        workspace=workspace,
    )


def bounded_report_text(text: str) -> str:
    """写入 Trace 的有界报告摘录。"""
    if len(text) <= _MAX_REPORT_CHARS:
        return text
    return text[:_MAX_REPORT_CHARS]
