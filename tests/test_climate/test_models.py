"""CTX-001：WorkspaceIndex / RunContext v2 严格校验与确定性序列化。"""

from __future__ import annotations

import json
from copy import deepcopy
from typing import Any

import pytest
from pydantic import ValidationError

from openharness.climate.models import (
    RunContext,
    WorkspaceIndex,
    dumps_climate_json,
    loads_run_context,
    loads_workspace_index,
)

RUN_ID = "0e8e6eb4-93f2-4ce7-8d22-91a28fa99314"
SHA256 = "sha256:" + ("a" * 64)
CREATED = "2026-08-22T14:00:00Z"
UPDATED = "2026-08-22T14:03:00Z"


def _minimal_index(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema_version": 1,
        "version": 1,
        "active_run_id": None,
        "run_ids": [],
        "updated_at": CREATED,
    }
    payload.update(overrides)
    return payload


def _minimal_run(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema_version": 2,
        "version": 1,
        "run_id": RUN_ID,
        "objective": "分析示例温度序列并生成报告",
        "status": "initialized",
        "created_at": CREATED,
        "updated_at": CREATED,
        "steps": [],
        "artifacts": [],
        "events": [
            {
                "sequence": 1,
                "timestamp": CREATED,
                "type": "run_created",
                "step_id": None,
                "data": {},
            }
        ],
        "last_error": None,
    }
    payload.update(overrides)
    return payload


def _full_run() -> dict[str, Any]:
    return {
        "schema_version": 2,
        "version": 4,
        "run_id": RUN_ID,
        "objective": "分析示例温度序列并生成报告",
        "status": "running",
        "created_at": CREATED,
        "updated_at": UPDATED,
        "steps": [
            {
                "step_id": "acquire",
                "action": "acquire_data",
                "title": "获取数据",
                "depends_on": [],
                "status": "succeeded",
                "attempts": 1,
                "input_hash": SHA256,
                "started_at": "2026-08-22T14:01:00Z",
                "finished_at": "2026-08-22T14:01:01Z",
                "result": {"artifact_ids": ["data-primary"]},
                "error": None,
            },
            {
                "step_id": "inspect",
                "action": "inspect_dataset",
                "title": "检查数据",
                "depends_on": ["acquire"],
                "status": "pending",
                "attempts": 0,
                "input_hash": None,
                "started_at": None,
                "finished_at": None,
                "result": None,
                "error": None,
            },
        ],
        "artifacts": [
            {
                "artifact_id": "data-primary",
                "kind": "dataset",
                "path": f".climate/data/{RUN_ID}/sample.csv",
                "media_type": "text/csv",
                "size_bytes": 120,
                "sha256": SHA256,
                "created_by_step": "acquire",
                "created_at": "2026-08-22T14:01:01Z",
            }
        ],
        "events": [
            {
                "sequence": 1,
                "timestamp": CREATED,
                "type": "run_created",
                "step_id": None,
                "data": {},
            },
            {
                "sequence": 2,
                "timestamp": "2026-08-22T14:01:00Z",
                "type": "step_started",
                "step_id": "acquire",
                "data": {},
            },
            {
                "sequence": 3,
                "timestamp": "2026-08-22T14:01:01Z",
                "type": "step_succeeded",
                "step_id": "acquire",
                "data": {"artifact_ids": ["data-primary"]},
            },
        ],
        "last_error": None,
    }


def test_context_v2_invariants_and_roundtrip() -> None:
    """CTX-001：最小/完整合法对象 round-trip，字节与对象一致。"""
    index = WorkspaceIndex.model_validate(
        _minimal_index(
            version=3,
            active_run_id=RUN_ID,
            run_ids=[RUN_ID],
            updated_at=UPDATED,
        )
    )
    assert index.schema_version == 1
    assert index.version == 3
    assert index.active_run_id == RUN_ID

    index_text = dumps_climate_json(index)
    assert index_text.endswith("\n")
    assert "\t" not in index_text
    assert json.loads(index_text) == json.loads(dumps_climate_json(index))
    # 两空格缩进
    assert '{\n  "active_run_id"' in index_text or '{\n  "schema_version"' in index_text
    assert dumps_climate_json(loads_workspace_index(index_text)) == index_text

    run = RunContext.model_validate(_full_run())
    run_text = dumps_climate_json(run)
    assert run_text.endswith("\n")
    assert dumps_climate_json(loads_run_context(run_text)) == run_text
    again = loads_run_context(run_text)
    assert again.model_dump(mode="json") == run.model_dump(mode="json")

    minimal = RunContext.model_validate(_minimal_run())
    assert minimal.version == 1
    assert minimal.status == "initialized"
    assert dumps_climate_json(loads_run_context(dumps_climate_json(minimal))) == dumps_climate_json(
        minimal
    )


def test_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        WorkspaceIndex.model_validate({**_minimal_index(), "extra_field": 1})
    with pytest.raises(ValidationError):
        RunContext.model_validate({**_minimal_run(), "mystery": True})
    payload = _full_run()
    payload["steps"][0]["unexpected"] = "x"
    with pytest.raises(ValidationError):
        RunContext.model_validate(payload)


def test_rejects_invalid_uuid_and_time_and_enums() -> None:
    with pytest.raises(ValidationError):
        WorkspaceIndex.model_validate(_minimal_index(active_run_id="not-a-uuid", run_ids=["not-a-uuid"]))
    with pytest.raises(ValidationError):
        # 非 v4（version nibble 不是 4）
        WorkspaceIndex.model_validate(
            _minimal_index(
                active_run_id="0e8e6eb4-93f2-3ce7-8d22-91a28fa99314",
                run_ids=["0e8e6eb4-93f2-3ce7-8d22-91a28fa99314"],
            )
        )
    with pytest.raises(ValidationError):
        WorkspaceIndex.model_validate(_minimal_index(updated_at="2026-08-22T14:00:00+00:00"))
    with pytest.raises(ValidationError):
        WorkspaceIndex.model_validate(_minimal_index(updated_at="2026-08-22 14:00:00Z"))
    with pytest.raises(ValidationError):
        RunContext.model_validate(_minimal_run(status="paused"))
    with pytest.raises(ValidationError):
        RunContext.model_validate(_minimal_run(run_id="UPPER-CASE-NOT-ALLOWED"))
    payload = _full_run()
    payload["steps"][0]["action"] = "download"
    with pytest.raises(ValidationError):
        RunContext.model_validate(payload)
    payload = _full_run()
    payload["artifacts"][0]["kind"] = "image"
    with pytest.raises(ValidationError):
        RunContext.model_validate(payload)
    payload = _full_run()
    payload["events"][0]["type"] = "unknown_event"
    with pytest.raises(ValidationError):
        RunContext.model_validate(payload)


def test_rejects_duplicate_and_broken_references() -> None:
    # active_run_id 必须属于 run_ids
    with pytest.raises(ValidationError):
        WorkspaceIndex.model_validate(_minimal_index(active_run_id=RUN_ID, run_ids=[]))
    # run_ids 去重
    with pytest.raises(ValidationError):
        WorkspaceIndex.model_validate(_minimal_index(run_ids=[RUN_ID, RUN_ID]))

    payload = _full_run()
    payload["steps"].append(deepcopy(payload["steps"][0]))
    with pytest.raises(ValidationError):
        RunContext.model_validate(payload)

    payload = _full_run()
    payload["artifacts"].append(deepcopy(payload["artifacts"][0]))
    with pytest.raises(ValidationError):
        RunContext.model_validate(payload)

    payload = _full_run()
    payload["steps"][1]["depends_on"] = ["missing-step"]
    with pytest.raises(ValidationError):
        RunContext.model_validate(payload)

    payload = _full_run()
    payload["artifacts"][0]["created_by_step"] = "missing-step"
    with pytest.raises(ValidationError):
        RunContext.model_validate(payload)

    payload = _full_run()
    payload["steps"][0]["result"] = {"artifact_ids": ["missing-artifact"]}
    with pytest.raises(ValidationError):
        RunContext.model_validate(payload)

    payload = _full_run()
    payload["events"][1]["step_id"] = "missing-step"
    with pytest.raises(ValidationError):
        RunContext.model_validate(payload)

    # 依赖成环
    payload = _full_run()
    payload["steps"][0]["depends_on"] = ["inspect"]
    with pytest.raises(ValidationError):
        RunContext.model_validate(payload)


def test_rejects_non_contiguous_event_sequence() -> None:
    payload = _full_run()
    payload["events"][1]["sequence"] = 3
    with pytest.raises(ValidationError):
        RunContext.model_validate(payload)

    payload = _full_run()
    payload["events"][0]["sequence"] = 0
    with pytest.raises(ValidationError):
        RunContext.model_validate(payload)

    payload = _minimal_run(events=[])
    # 允许空 events；若有事件必须从 1 连续
    RunContext.model_validate(payload)


def test_version_and_time_invariants() -> None:
    with pytest.raises(ValidationError):
        WorkspaceIndex.model_validate(_minimal_index(version=0))
    with pytest.raises(ValidationError):
        RunContext.model_validate(_minimal_run(version=0))
    with pytest.raises(ValidationError):
        RunContext.model_validate(_minimal_run(updated_at="2026-08-22T13:59:59Z"))
    with pytest.raises(ValidationError):
        RunContext.model_validate(_minimal_run(schema_version=1))
    with pytest.raises(ValidationError):
        WorkspaceIndex.model_validate(_minimal_index(schema_version=2))

    # 合法初始 version=1，created_at == updated_at
    run = RunContext.model_validate(_minimal_run(version=1))
    assert run.version == 1
    assert run.created_at == run.updated_at


def test_rejects_unsafe_artifact_path_and_bad_hash() -> None:
    payload = _full_run()
    payload["artifacts"][0]["path"] = "../outside.csv"
    with pytest.raises(ValidationError):
        RunContext.model_validate(payload)
    payload = _full_run()
    payload["artifacts"][0]["path"] = f"E:/abs/{RUN_ID}/x.csv"
    with pytest.raises(ValidationError):
        RunContext.model_validate(payload)
    payload = _full_run()
    payload["artifacts"][0]["sha256"] = "deadbeef"
    with pytest.raises(ValidationError):
        RunContext.model_validate(payload)


def test_structured_error_shape() -> None:
    payload = _minimal_run(
        status="failed",
        last_error={
            "code": "CLIMATE_DATA_INVALID",
            "message": "数据无效",
            "retryable": False,
            "details": {"field": "csv"},
        },
    )
    run = RunContext.model_validate(payload)
    assert run.last_error is not None
    assert run.last_error.code == "CLIMATE_DATA_INVALID"

    bad = _minimal_run(last_error={"code": "CLIMATE_DATA_INVALID", "message": "x"})
    with pytest.raises(ValidationError):
        RunContext.model_validate(bad)
    with pytest.raises(ValidationError):
        RunContext.model_validate(
            _minimal_run(
                last_error={
                    "code": "NOT_A_REAL_CODE",
                    "message": "x",
                    "retryable": False,
                    "details": {},
                }
            )
        )
