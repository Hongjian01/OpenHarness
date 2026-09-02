"""G4 real_agent 非敏感配置：加载、指纹、拒绝凭证字段。"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

_SECRET_KEY = re.compile(r"(?i)^(api[_-]?key|token|password|secret|authorization|cdsapirc)$")
_SK_TOKEN = re.compile(r"(?i)sk-[A-Za-z0-9_-]{8,}")
REQUIRED_RUNS = 3
MIN_PASSES = 2


class CdsSmokeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dataset: str
    variables: list[str] = Field(min_length=1, max_length=1)
    area: list[float] = Field(min_length=4, max_length=4)
    date_start: str
    date_end: str
    format: str
    allow_sample_fallback: bool = False

    @field_validator("allow_sample_fallback")
    @classmethod
    def _no_fallback(cls, value: bool) -> bool:
        if value is not False:
            raise ValueError("real_agent 场景禁止 sample fallback")
        return value

    @field_validator("date_end")
    @classmethod
    def _same_day_placeholder(cls, value: str) -> str:
        return value


class ClimateRealConfig(BaseModel):
    """agent-config 只含非敏感引用，不含 key。"""

    model_config = ConfigDict(extra="forbid")

    schema_version: str
    profile: str
    provider: str
    model: str
    effort: str
    max_turns: int = Field(ge=1, le=200)
    permission_mode: str
    timeout_seconds: int = Field(ge=1, le=3600)
    scenario_id: str
    skill: str
    allow_sample_fallback: bool = False
    cds_request: CdsSmokeRequest

    @field_validator("allow_sample_fallback")
    @classmethod
    def _top_no_fallback(cls, value: bool) -> bool:
        if value is not False:
            raise ValueError("real_agent 禁止 fallback")
        return value

    @model_validator(mode="after")
    def _one_day(self) -> ClimateRealConfig:
        if self.cds_request.date_start != self.cds_request.date_end:
            raise ValueError("最小 smoke 日期必须为 1 天")
        return self


def load_agent_config(path: Path) -> ClimateRealConfig:
    """加载并拒绝敏感键/疑似密钥。"""
    text = path.read_text(encoding="utf-8")
    _reject_secrets(text)
    payload = json.loads(text)
    if not isinstance(payload, dict):
        raise ValueError("agent-config 必须是对象")
    for key in payload:
        if _SECRET_KEY.search(str(key)):
            raise ValueError(f"agent-config 含敏感键: {key}")
    return ClimateRealConfig.model_validate(payload)


def config_fingerprint(
    config: ClimateRealConfig,
    *,
    scenario_text: str,
    skill_text: str,
    git_commit: str,
) -> str:
    """代码/config/scenario/skill/commit 任一变化都改变指纹，三次必须重计。"""
    payload = {
        "config": config.model_dump(mode="json"),
        "scenario": scenario_text,
        "skill": skill_text,
        "commit": git_commit,
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def public_config_summary(config: ClimateRealConfig) -> dict[str, Any]:
    """写入 baseline 的非敏感摘要。"""
    return config.model_dump(mode="json")


def _reject_secrets(text: str) -> None:
    if _SK_TOKEN.search(text):
        raise ValueError("agent-config 含疑似密钥")
    if ".cdsapirc" in text.lower():
        raise ValueError("agent-config 不得引用 .cdsapirc")
