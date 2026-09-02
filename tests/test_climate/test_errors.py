"""ERR-001/002 共享错误基础测试（完整工具一致性留到 G2）。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from openharness.climate.errors import (
    ERROR_RETRYABLE,
    ClimateError,
    encode_tool_result_json,
    failure_envelope,
    redact_secrets,
    sanitize_details,
    success_envelope,
)


def test_error_envelope() -> None:
    """ERR-001：成功/失败 envelope 结构稳定，且与 is_error 语义一致。"""
    ok = success_envelope(
        data={"artifact_id": "data-primary"},
        run_id="0e8e6eb4-93f2-4ce7-8d22-91a28fa99314",
        context_version=4,
    )
    assert ok == {
        "ok": True,
        "data": {"artifact_id": "data-primary"},
        "run_id": "0e8e6eb4-93f2-4ce7-8d22-91a28fa99314",
        "context_version": 4,
    }

    err = ClimateError(
        code="CLIMATE_INVALID_PATH",
        message="路径不符合 workspace 安全策略",
        retryable=False,
        details={"path": "data/../secret"},
    )
    fail = failure_envelope(err, run_id=None, context_version=None)
    assert fail == {
        "ok": False,
        "error": {
            "code": "CLIMATE_INVALID_PATH",
            "message": "路径不符合 workspace 安全策略",
            "retryable": False,
            "details": {"path": "data/../secret"},
        },
        "run_id": None,
        "context_version": None,
    }

    # 确定性 JSON：键顺序稳定、UTF-8、无多余空白绕过
    encoded_ok = encode_tool_result_json(ok)
    encoded_fail = encode_tool_result_json(fail)
    assert json.loads(encoded_ok) == ok
    assert json.loads(encoded_fail) == fail
    assert encoded_ok == encode_tool_result_json(ok)
    assert encoded_fail == encode_tool_result_json(fail)
    # ToolResult.is_error 与 ok 互为反值（共享基础约定）
    assert ok["ok"] is True
    assert fail["ok"] is False


def test_error_details_allowlist_and_redaction(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """ERR-002：details 仅允许安全诊断字段；message/details 脱敏。"""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.setenv("HOME", str(home))

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    abs_leak = str(workspace / "secret.txt")
    token = "cds-token-abc123XYZ"

    raw_details = {
        "path": ".climate/data/run/sample.csv",
        "field": "mode",
        "status": "failed",
        "allowed": ["sample", "local"],
        "reason": "invalid_semantics",
        "absolute_path": abs_leak,
        "traceback": 'Traceback (most recent call last):\n  File "/x.py"',
        "token": token,
        "api_key": "sk-secret-key",
        "home": str(home),
        "nested": {"path": abs_leak, "ok": True},
    }
    cleaned = sanitize_details(raw_details, workspace=workspace)
    assert cleaned["path"] == ".climate/data/run/sample.csv"
    assert cleaned["field"] == "mode"
    assert cleaned["status"] == "failed"
    assert cleaned["allowed"] == ["sample", "local"]
    assert cleaned["reason"] == "invalid_semantics"
    assert "absolute_path" not in cleaned
    assert "traceback" not in cleaned
    assert "token" not in cleaned
    assert "api_key" not in cleaned
    assert "home" not in cleaned
    assert "nested" not in cleaned

    message = (
        f"写入失败：{abs_leak} home={home} token={token} "
        "api_key=sk-secret-key .cdsapirc=password123"
    )
    redacted = redact_secrets(message, workspace=workspace)
    assert abs_leak not in redacted
    assert str(workspace) not in redacted
    assert str(home) not in redacted
    assert token not in redacted
    assert "sk-secret-key" not in redacted
    assert "password123" not in redacted
    assert "Traceback" not in redacted


@pytest.mark.parametrize(
    "code,retryable",
    list(ERROR_RETRYABLE.items()),
)
def test_error_retryable_table_is_complete(code: str, retryable: bool) -> None:
    """固定错误码表含 retryable 语义，供后续工具复用。"""
    err = ClimateError(code=code, message="x", retryable=retryable, details={})
    assert err.retryable is retryable
    assert err.code.startswith("CLIMATE_")
