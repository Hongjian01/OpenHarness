"""Climate Eval runner：加载 scenario、调用 adapter、硬断言、原子写报告。"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from openharness.utils.fs import atomic_write_text

from evals.climate.assertions import WIRING_ASSERTION_TYPES, evaluate_hard_assertions
from evals.climate.models import EvalMode, Scenario, TraceRecord, load_scenario
from evals.climate.real_offline import run_real_offline

ROOT = Path(__file__).resolve().parents[2]
SCENARIO_DIR = ROOT / "evals" / "climate" / "scenarios"
REPORT_DIR = ROOT / "evals" / "reports"
SUITE_VERSION = "g3-foundation"

SYNTHETIC_NOTICE = (
    "SYNTHETIC DRY-RUN: tools and models were not executed / "
    "synthetic 干跑：未执行工具或模型。This result does not count toward real pass rate。"
)

_KNOWN_SUITES = frozenset({"climate"})


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="evals", description="ClimWorkflow Eval runner")
    parser.add_argument("--suite", required=True, help="评测套件，例如 climate")
    parser.add_argument(
        "--mode",
        required=True,
        choices=["real_offline", "synthetic_dry_run", "real_agent"],
        help="执行模式",
    )
    parser.add_argument("--scenario", default=None, help="可选，指定单个 scenario id")
    args = parser.parse_args(argv)
    return run_suite(args.suite, args.mode, scenario_id=args.scenario)


def run_suite(suite: str, mode: str, scenario_id: str | None = None) -> int:
    """执行套件并返回进程退出码。"""
    if suite not in _KNOWN_SUITES:
        _emit_error("CLIMATE_INVALID_INPUT", f"unknown suite: {suite}")
        return 2
    try:
        eval_mode = EvalMode(mode)
    except ValueError:
        _emit_error("CLIMATE_INVALID_INPUT", f"unknown mode: {mode}")
        return 2

    if eval_mode is EvalMode.real_agent:
        _emit_error(
            "CLIMATE_DEPENDENCY_MISSING",
            "G4 尚未配置：real_agent 不可执行，不得伪造工具或模型运行，不计入通过率。",
        )
        return 2

    try:
        scenarios = _load_suite_scenarios(scenario_id, mode=eval_mode)
    except FileNotFoundError as exc:
        _emit_error("CLIMATE_INVALID_INPUT", str(exc))
        return 2

    if eval_mode is EvalMode.real_offline:
        return _run_real_offline_suite(suite, scenarios)

    traces: list[dict[str, Any]] = []
    failed = False
    for scenario in scenarios:
        trace = _run_synthetic(scenario)
        wiring = [item for item in scenario.hard_assertions if item.type in WIRING_ASSERTION_TYPES]
        results = evaluate_hard_assertions(trace, wiring)
        trace = trace.model_copy(update={"assertion_results": results})
        traces.append(
            {
                "trace": json.loads(trace.model_dump_json()),
                "passed": all(item.passed for item in results),
            }
        )
        if any(item.passed is False for item in results):
            failed = True

    report = {
        "suite": suite,
        "mode": eval_mode.value,
        "synthetic": True,
        "tools_executed": False,
        "model_invoked": False,
        "counts_toward_real_pass_rate": False,
        "real_pass_rate": None,
        "notice": SYNTHETIC_NOTICE,
        "traces": traces,
    }
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    report_path = REPORT_DIR / f"{suite}-{eval_mode.value}.json"
    payload = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    atomic_write_text(report_path, payload)
    print(SYNTHETIC_NOTICE)
    print(f"wrote {report_path.as_posix()}")
    if failed:
        print("hard assertion failed")
        return 1
    return 0


_REAL_OFFLINE_ORDER = (
    "sample_pipeline",
    "cached_inspect",
    "multiturn_recovery",
    "pre_tool_output_guard",
)


def _load_suite_scenarios(scenario_id: str | None, *, mode: EvalMode) -> list[Scenario]:
    if not SCENARIO_DIR.is_dir():
        raise FileNotFoundError(f"scenario directory not found: {SCENARIO_DIR}")
    files = sorted(SCENARIO_DIR.glob("*.yaml"))
    loaded = [load_scenario(path) for path in files]
    if scenario_id is None:
        if mode is EvalMode.real_offline:
            by_id = {item.id: item for item in loaded}
            matched = []
            for sid in _REAL_OFFLINE_ORDER:
                if sid not in by_id:
                    raise FileNotFoundError(f"scenario not found: {sid}")
                matched.append(by_id[sid])
            return matched
        matched = [item for item in loaded if item.id == "sample_pipeline"]
        if not matched:
            raise FileNotFoundError("scenario not found: sample_pipeline")
        return matched
    matched = [item for item in loaded if item.id == scenario_id]
    if not matched:
        raise FileNotFoundError(f"scenario not found: {scenario_id}")
    if mode is EvalMode.real_offline and matched[0].mode is not EvalMode.real_offline:
        raise FileNotFoundError(f"scenario not found: {scenario_id}")
    return matched


def _run_real_offline_suite(suite: str, scenarios: list[Scenario]) -> int:
    traces: list[dict[str, Any]] = []
    failed = False
    real_passed = 0
    for scenario in scenarios:
        with tempfile.TemporaryDirectory(prefix="climate-eval-") as tmp:
            workspace = Path(tmp) / "ws"
            workspace.mkdir()
            trace = run_real_offline(scenario, workspace=workspace)
            results = evaluate_hard_assertions(trace, list(scenario.hard_assertions))
            trace = trace.model_copy(update={"assertion_results": results})
            passed = all(item.passed for item in results)
            traces.append({"trace": json.loads(trace.model_dump_json()), "passed": passed})
            if passed:
                real_passed += 1
            else:
                failed = True

    total = len(scenarios)
    real_pass_rate = (real_passed / total) if total else None
    report = {
        "suite": suite,
        "mode": EvalMode.real_offline.value,
        "synthetic": False,
        "tools_executed": True,
        "model_invoked": False,
        "counts_toward_real_pass_rate": True,
        "real_pass_rate": real_pass_rate,
        "notice": "real_offline: Climate tools executed without network or model.",
        "traces": traces,
    }
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    report_path = REPORT_DIR / f"{suite}-{EvalMode.real_offline.value}.json"
    payload = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    atomic_write_text(report_path, payload)
    print(f"wrote {report_path.as_posix()}")
    print(f"real_pass_rate={real_pass_rate}")
    if failed:
        print("hard assertion failed")
        return 1
    return 0


def _run_synthetic(scenario: Scenario) -> TraceRecord:
    """只生成 wiring 验证数据，明确不执行工具/模型。"""
    now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    tool_calls = []
    for index, name in enumerate(scenario.expected_tool_sequence, start=1):
        tool_calls.append(
            {
                "sequence": index,
                "name": name,
                "input_redacted": {"synthetic": True, "note": "not executed"},
                "is_error": False,
                "error_code": None,
                "duration_ms": 0,
            }
        )
    return TraceRecord.model_validate(
        {
            "suite_version": SUITE_VERSION,
            "scenario_id": scenario.id,
            "run_id": None,
            "mode": EvalMode.synthetic_dry_run,
            "started_at": now,
            "finished_at": now,
            "duration_ms": 0,
            "tool_calls": tool_calls,
            "hook_events": [],
            "final_run_status": "not_executed",
            "final_context_version": None,
            "artifact_manifest": [],
            "assertion_results": [],
            "synthetic": True,
            "tools_executed": False,
            "model_invoked": False,
            "counts_toward_real_pass_rate": False,
        }
    )


def _emit_error(code: str, message: str) -> None:
    print(f"{code}: {message}", file=sys.stderr)
