"""Climate Eval Scenario 与 TraceRecord 严格 schema。"""

from __future__ import annotations

import json
import os
import re
from enum import Enum
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

_SECRET_KEY = re.compile(r"(?i)(api[_-]?key|token|password|secret|authorization|cdsapirc)")
_SK_TOKEN = re.compile(r"(?i)sk-[A-Za-z0-9_-]{8,}")


class EvalMode(str, Enum):
    """SPEC §12.1 允许的执行模式。"""

    real_offline = "real_offline"
    synthetic_dry_run = "synthetic_dry_run"
    real_agent = "real_agent"


class ScenarioTurn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: str = Field(min_length=1, max_length=32)
    content: str = Field(min_length=1, max_length=12000)


class HardAssertionSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=64)
    type: str = Field(min_length=1, max_length=64)
    expected: Any


class ScenarioToolInvocation(BaseModel):
    """real_offline 逐步调用真实工具的输入；synthetic 可缺省。"""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=128)
    input: dict[str, Any] = Field(default_factory=dict)
    session: int = Field(default=1, ge=1, le=8)


class Scenario(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=128)
    description: str = Field(min_length=1, max_length=4000)
    mode: EvalMode
    initial_files: dict[str, str]
    turns: list[ScenarioTurn] = Field(min_length=1)
    expected_tool_sequence: list[str] = Field(min_length=1)
    hard_assertions: list[HardAssertionSpec] = Field(min_length=1)
    timeout_seconds: int = Field(ge=1, le=3600)
    tool_invocations: list[ScenarioToolInvocation] = Field(default_factory=list)
    fixture_files: dict[str, str] = Field(default_factory=dict)

    @field_validator("expected_tool_sequence")
    @classmethod
    def _sequence_items(cls, value: list[str]) -> list[str]:
        for item in value:
            if not item or not item.strip():
                raise ValueError("expected_tool_sequence 项不得为空")
        return value

    @field_validator("fixture_files")
    @classmethod
    def _fixture_names(cls, value: dict[str, str]) -> dict[str, str]:
        for dest, name in value.items():
            dest_path = Path(dest.replace("\\", "/"))
            if dest.startswith("/") or dest.startswith("\\") or ".." in dest_path.parts:
                raise ValueError("fixture 目标路径不安全")
            if not name or "/" in name or "\\" in name or name.startswith("."):
                raise ValueError("fixture 文件名非法")
        return value


class ToolCallTrace(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sequence: int = Field(ge=1)
    name: str = Field(min_length=1)
    input_redacted: dict[str, Any]
    is_error: bool
    error_code: str | None = None
    duration_ms: int = Field(ge=0)
    context_version: int | None = None
    output_redacted: dict[str, Any] = Field(default_factory=dict)
    session: int = Field(default=1, ge=1)

    @model_validator(mode="after")
    def _input_is_redacted(self) -> ToolCallTrace:
        _reject_sensitive_payload(self.input_redacted)
        _reject_sensitive_payload(self.output_redacted)
        return self


class HookEventTrace(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sequence: int = Field(ge=1)
    event: str = Field(min_length=1)
    tool_name: str = Field(min_length=1)
    blocked: bool
    reason_code: str | None = None


class AssertionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    type: str
    passed: bool
    message: str


class TraceRecord(BaseModel):
    """SPEC §12.1 TraceRecord，并带 EVAL-003 的 synthetic 标记。"""

    model_config = ConfigDict(extra="forbid")

    suite_version: str = Field(min_length=1)
    scenario_id: str = Field(min_length=1)
    run_id: str | None
    mode: EvalMode
    started_at: str = Field(min_length=1)
    finished_at: str = Field(min_length=1)
    duration_ms: int = Field(ge=0)
    tool_calls: list[ToolCallTrace]
    hook_events: list[HookEventTrace]
    final_run_status: str | None
    final_context_version: int | None
    artifact_manifest: list[dict[str, Any]]
    assertion_results: list[AssertionResult]
    synthetic: bool
    tools_executed: bool
    model_invoked: bool
    counts_toward_real_pass_rate: bool
    network_isolated: bool = False
    context_versions: list[int] = Field(default_factory=list)
    recovery: dict[str, Any] | None = None

    @model_validator(mode="after")
    def _synthetic_cannot_count(self) -> TraceRecord:
        if self.synthetic and self.counts_toward_real_pass_rate:
            raise ValueError("synthetic Trace 不得计入真实通过率")
        if self.synthetic and (self.tools_executed or self.model_invoked):
            raise ValueError("synthetic Trace 不得声称已执行工具或模型")
        if self.mode is EvalMode.real_offline and self.synthetic:
            raise ValueError("real_offline Trace 不得标记 synthetic")
        if self.recovery is not None:
            _reject_sensitive_payload(self.recovery)
        encoded = json.dumps(self.model_dump(mode="json"), ensure_ascii=False)
        _reject_sensitive_text(encoded)
        return self


def load_scenario(path: Path) -> Scenario:
    """从 YAML 加载并严格校验 Scenario。"""
    raw = path.read_text(encoding="utf-8")
    payload = yaml.safe_load(raw)
    if not isinstance(payload, dict):
        raise ValueError(f"scenario 必须是映射: {path}")
    return Scenario.model_validate(payload)


def _home_strings() -> list[str]:
    values: list[str] = []
    try:
        values.append(str(Path.home()))
    except (RuntimeError, OSError):
        pass
    for key in ("USERPROFILE", "HOME"):
        item = os.environ.get(key)
        if item:
            values.append(item)
    return values


def _reject_sensitive_text(text: str) -> None:
    lowered = text.lower()
    if _SK_TOKEN.search(text):
        raise ValueError("Trace 含疑似密钥，拒绝持久化")
    if ".cdsapirc" in lowered:
        raise ValueError("Trace 不得包含 .cdsapirc")
    for home in _home_strings():
        if home and home in text:
            raise ValueError("Trace 不得包含用户主目录或绝对路径")


def _reject_sensitive_payload(payload: Any) -> None:
    if isinstance(payload, dict):
        for key, value in payload.items():
            if _SECRET_KEY.search(str(key)):
                raise ValueError(f"input_redacted 含敏感键: {key}")
            _reject_sensitive_payload(value)
        return
    if isinstance(payload, list):
        for item in payload:
            _reject_sensitive_payload(item)
        return
    if isinstance(payload, str):
        _reject_sensitive_text(payload)
