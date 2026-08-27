"""CTX-002/003、IO-001、LOCK-001、CON-001、MIG/REC、TEST-002：Repository 测试。"""

from __future__ import annotations

import contextlib
import hashlib
import json
import threading
from pathlib import Path
from typing import Any

import pytest

from openharness.climate.errors import ClimateError
from openharness.climate.models import RunContext, WorkspaceIndex
from openharness.climate.repository import ContextRepository
from openharness.utils import file_lock as exclusive_file_lock_mod
from openharness.utils import fs as fs_mod
from openharness.utils.file_lock import SwarmLockUnavailableError

RUN_ID = "0e8e6eb4-93f2-4ce7-8d22-91a28fa99314"
RUN_ID_B = "1f9f7fc5-a4e3-4df8-9e33-a2b39fb0a425"
CREATED = "2026-08-22T14:00:00Z"
FIXTURES = Path(__file__).resolve().parent / "fixtures"
V1_FIXTURE = FIXTURES / "run_context_v1.json"
SAMPLE_CSV = b"date,temperature_c\n2026-01-01,1.0\n"


def _index(**overrides: Any) -> WorkspaceIndex:
    payload: dict[str, Any] = {
        "schema_version": 1,
        "version": 1,
        "active_run_id": None,
        "run_ids": [],
        "updated_at": CREATED,
    }
    payload.update(overrides)
    return WorkspaceIndex.model_validate(payload)


def _run(**overrides: Any) -> RunContext:
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
    return RunContext.model_validate(payload)


def _layout_paths(workspace: Path) -> dict[str, Path]:
    root = workspace / ".climate"
    return {
        "root": root,
        "index": root / "index.json",
        "runs": root / "runs",
        "data": root / "data",
        "output": root / "output",
        "locks": root / "locks",
        "transactions": root / "transactions",
        "backups": root / "backups",
        "workspace_lock": root / "locks" / "workspace.lock",
        "run_lock": root / "locks" / f"{RUN_ID}.lock",
        "run_context": root / "runs" / RUN_ID / "context.json",
    }


def test_ensure_layout_creates_fixed_dirs(tmp_path: Path) -> None:
    workspace = (tmp_path / "ws").resolve()
    workspace.mkdir()
    repo = ContextRepository(workspace)
    repo.ensure_layout()

    paths = _layout_paths(workspace)
    for key in ("root", "runs", "data", "output", "locks", "transactions", "backups"):
        assert paths[key].is_dir()


def test_context_is_authoritative_across_new_session(tmp_path: Path) -> None:
    """CTX-002：新 Repository 实例读取磁盘 Context，而非会话内存。"""
    workspace = (tmp_path / "ws").resolve()
    workspace.mkdir()
    repo_a = ContextRepository(workspace)
    repo_a.ensure_layout()

    saved_index = repo_a.save_index(
        _index(active_run_id=RUN_ID, run_ids=[RUN_ID]),
        expected_version=None,
    )
    assert saved_index.version == 1
    saved_run = repo_a.save_run(_run(), expected_version=None)
    assert saved_run.version == 1

    # 模拟新会话：全新实例，不共享内存
    repo_b = ContextRepository(workspace)
    loaded_index = repo_b.load_index()
    loaded_run = repo_b.load_run(RUN_ID)
    assert loaded_index.model_dump(mode="json") == saved_index.model_dump(mode="json")
    assert loaded_run.model_dump(mode="json") == saved_run.model_dump(mode="json")
    assert loaded_run.objective == "分析示例温度序列并生成报告"


def test_atomic_write_format_and_helper_used(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = (tmp_path / "ws").resolve()
    workspace.mkdir()
    repo = ContextRepository(workspace)
    repo.ensure_layout()

    calls: list[Path] = []
    real_atomic = fs_mod.atomic_write_text

    def tracking_atomic(path: Any, data: str, **kwargs: Any) -> None:
        calls.append(Path(path))
        # 契约：UTF-8、两空格、稳定键、末尾换行
        assert data.endswith("\n")
        assert data.encode("utf-8").decode("utf-8") == data
        parsed = json.loads(data)
        assert data == json.dumps(parsed, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        return real_atomic(path, data, **kwargs)

    monkeypatch.setattr("openharness.climate.repository.atomic_write_text", tracking_atomic)

    repo.save_index(_index(), expected_version=None)
    repo.save_run(_run(), expected_version=None)

    paths = _layout_paths(workspace)
    assert paths["index"] in calls
    assert paths["run_context"] in calls
    assert paths["index"].read_text(encoding="utf-8").endswith("\n")
    assert paths["run_context"].read_text(encoding="utf-8").endswith("\n")


def test_atomic_publish_failure_preserves_stable_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """IO-001：os.replace 失败时保留最后稳定文件并清理临时文件。"""
    workspace = (tmp_path / "ws").resolve()
    workspace.mkdir()
    repo = ContextRepository(workspace)
    repo.ensure_layout()
    repo.save_index(_index(version=1), expected_version=None)

    paths = _layout_paths(workspace)
    stable = paths["index"].read_bytes()

    def boom_replace(src: Any, dst: Any) -> None:
        raise OSError("simulated replace failure")

    monkeypatch.setattr(fs_mod.os, "replace", boom_replace)

    with pytest.raises(ClimateError) as exc_info:
        repo.save_index(
            _index(version=1, updated_at="2026-08-22T15:00:00Z", run_ids=[RUN_ID], active_run_id=RUN_ID),
            expected_version=1,
        )
    err = exc_info.value
    assert err.code == "CLIMATE_WRITE_FAILED"
    assert err.retryable is True
    assert paths["index"].read_bytes() == stable
    leftovers = [
        p
        for p in paths["root"].rglob("*")
        if p.is_file() and p.suffix == ".tmp"
    ]
    assert leftovers == []
    # 错误消息不得含绝对路径
    assert str(workspace) not in err.message
    assert "Traceback" not in err.message


def test_expected_version_conflict_does_not_write(tmp_path: Path) -> None:
    """CON-001：expected_version 不匹配时不写文件。"""
    workspace = (tmp_path / "ws").resolve()
    workspace.mkdir()
    repo = ContextRepository(workspace)
    repo.ensure_layout()
    repo.save_run(_run(version=1), expected_version=None)
    paths = _layout_paths(workspace)
    before = paths["run_context"].read_bytes()

    mutated = _run(version=1, objective="被错误覆盖", updated_at="2026-08-22T15:00:00Z")
    with pytest.raises(ClimateError) as exc_info:
        repo.save_run(mutated, expected_version=99)
    err = exc_info.value
    assert err.code == "CLIMATE_VERSION_CONFLICT"
    assert err.retryable is True
    assert err.details.get("expected_version") == 99
    assert err.details.get("actual_version") == 1
    assert paths["run_context"].read_bytes() == before

    saved = repo.save_run(
        _run(version=1, objective="合法更新", updated_at="2026-08-22T15:00:00Z"),
        expected_version=1,
    )
    assert saved.version == 2
    assert saved.objective == "合法更新"
    assert json.loads(paths["run_context"].read_text(encoding="utf-8"))["version"] == 2


def test_lock_unavailable_maps_to_stable_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = (tmp_path / "ws").resolve()
    workspace.mkdir()
    repo = ContextRepository(workspace)
    repo.ensure_layout()

    def boom_lock(*_args: Any, **_kwargs: Any):
        raise SwarmLockUnavailableError("file locking is not supported")

    monkeypatch.setattr("openharness.climate.repository.exclusive_file_lock", boom_lock)

    with pytest.raises(ClimateError) as exc_info:
        repo.save_index(_index(), expected_version=None)
    assert exc_info.value.code == "CLIMATE_LOCK_FAILED"
    assert exc_info.value.retryable is True


def test_concurrent_updates_follow_lock_order(tmp_path: Path) -> None:
    """LOCK-001：并发更新不丢写、不死锁。"""
    workspace = (tmp_path / "ws").resolve()
    workspace.mkdir()
    repo = ContextRepository(workspace)
    repo.ensure_layout()
    repo.save_run(_run(version=1, objective="base"), expected_version=None)

    errors: list[BaseException] = []
    barrier = threading.Barrier(2)

    def worker(tag: str) -> None:
        local = ContextRepository(workspace)
        try:
            barrier.wait(timeout=5)
            for _ in range(20):
                while True:
                    current = local.load_run(RUN_ID)
                    try:
                        local.save_run(
                            current.model_copy(
                                update={
                                    "objective": f"{current.objective}|{tag}",
                                    "updated_at": "2026-08-22T16:00:00Z",
                                }
                            ),
                            expected_version=current.version,
                        )
                        break
                    except ClimateError as exc:
                        if exc.code != "CLIMATE_VERSION_CONFLICT":
                            raise
        except BaseException as exc:  # noqa: BLE001 — 收集线程异常
            errors.append(exc)

    threads = [
        threading.Thread(target=worker, args=("A",)),
        threading.Thread(target=worker, args=("B",)),
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)
        assert not t.is_alive(), "并发测试疑似死锁"

    assert errors == []
    final = repo.load_run(RUN_ID)
    # 40 次成功递增：初始 1 + 40 = 41
    assert final.version == 41
    assert final.objective.count("|A") == 20
    assert final.objective.count("|B") == 20


def test_active_run_acquires_workspace_before_run_lock(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """LOCK-001：active-run / recover 固定 workspace → run 锁序，禁止反向。"""
    workspace = (tmp_path / "ws").resolve()
    workspace.mkdir()
    repo = ContextRepository(workspace)
    repo.ensure_layout()

    acquired: list[str] = []
    real_lock = exclusive_file_lock_mod.exclusive_file_lock

    @contextlib.contextmanager
    def tracking_lock(lock_path: Any, **kwargs: Any):
        name = Path(lock_path).name
        acquired.append(f"acquire:{name}")
        with real_lock(lock_path, **kwargs):
            yield
        acquired.append(f"release:{name}")

    monkeypatch.setattr(
        "openharness.climate.repository.exclusive_file_lock", tracking_lock
    )

    repo.create_and_activate_run(_run(run_id=RUN_ID, objective="lock-order"))

    # 抽取 create 阶段（recover 可能先空跑）中涉及 workspace + run 的连续获取
    pairs = [
        (acquired[i], acquired[i + 1])
        for i in range(len(acquired) - 1)
        if acquired[i].startswith("acquire:") and acquired[i + 1].startswith("acquire:")
    ]
    assert ("acquire:workspace.lock", f"acquire:{RUN_ID}.lock") in pairs
    # 不得出现 run → workspace
    assert (f"acquire:{RUN_ID}.lock", "acquire:workspace.lock") not in pairs

    # 再验证 recover 在已有 marker 时同样遵守锁序
    acquired.clear()
    tx = "cccccccc-dddd-4eee-8fff-000000000000"
    _write_marker(
        workspace,
        transaction_id=tx,
        old_active_run_id=None,
        new_active_run_id=RUN_ID,
        run_context_written=True,
        index_written=True,
    )
    repo.recover_active_run_transactions()
    pairs_rec = [
        (acquired[i], acquired[i + 1])
        for i in range(len(acquired) - 1)
        if acquired[i].startswith("acquire:") and acquired[i + 1].startswith("acquire:")
    ]
    assert ("acquire:workspace.lock", f"acquire:{RUN_ID}.lock") in pairs_rec
    assert (f"acquire:{RUN_ID}.lock", "acquire:workspace.lock") not in pairs_rec


def test_read_failures_are_distinct_and_non_destructive(tmp_path: Path) -> None:
    """CTX-003：不存在 / 损坏 JSON / 不支持 schema 错误可区分且不覆盖。"""
    workspace = (tmp_path / "ws").resolve()
    workspace.mkdir()
    repo = ContextRepository(workspace)
    repo.ensure_layout()

    with pytest.raises(ClimateError) as missing:
        repo.load_run(RUN_ID)
    assert missing.value.code == "CLIMATE_RUN_NOT_FOUND"

    paths = _layout_paths(workspace)
    paths["run_context"].parent.mkdir(parents=True, exist_ok=True)

    # 无效 JSON
    paths["run_context"].write_text("{not-json", encoding="utf-8")
    corrupt_bytes = paths["run_context"].read_bytes()
    with pytest.raises(ClimateError) as bad_json:
        repo.load_run(RUN_ID)
    assert bad_json.value.code == "CLIMATE_CONTEXT_CORRUPT"
    assert bad_json.value.details.get("reason") == "invalid_json"
    assert paths["run_context"].read_bytes() == corrupt_bytes

    # 语义不一致：version=0 模型拒绝，直接写非法 JSON 对象
    paths["run_context"].write_text(
        json.dumps(
            {
                "schema_version": 2,
                "version": 0,
                "run_id": RUN_ID,
                "objective": "x",
                "status": "initialized",
                "created_at": CREATED,
                "updated_at": CREATED,
                "steps": [],
                "artifacts": [],
                "events": [],
                "last_error": None,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    semantic_bytes = paths["run_context"].read_bytes()
    with pytest.raises(ClimateError) as bad_sem:
        repo.load_run(RUN_ID)
    assert bad_sem.value.code == "CLIMATE_CONTEXT_CORRUPT"
    assert bad_sem.value.details.get("reason") == "invalid_semantics"
    assert paths["run_context"].read_bytes() == semantic_bytes

    # 不支持的 schema
    paths["run_context"].write_text(
        json.dumps(
            {
                "schema_version": 99,
                "version": 1,
                "run_id": RUN_ID,
                "objective": "x",
                "status": "initialized",
                "created_at": CREATED,
                "updated_at": CREATED,
                "steps": [],
                "artifacts": [],
                "events": [],
                "last_error": None,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    unsupported_bytes = paths["run_context"].read_bytes()
    with pytest.raises(ClimateError) as unsupported:
        repo.load_run(RUN_ID)
    assert unsupported.value.code == "CLIMATE_SCHEMA_UNSUPPORTED"
    assert unsupported.value.details.get("schema_version") == 99
    assert paths["run_context"].read_bytes() == unsupported_bytes

    # index 损坏同样不覆盖
    paths["index"].write_text("{broken", encoding="utf-8")
    index_bytes = paths["index"].read_bytes()
    with pytest.raises(ClimateError) as index_corrupt:
        repo.load_index()
    assert index_corrupt.value.code == "CLIMATE_CONTEXT_CORRUPT"
    assert paths["index"].read_bytes() == index_bytes


# ---------------------------------------------------------------------------
# Day 03：MIG-001 / REC-001 / REC-002 / REC-003
# ---------------------------------------------------------------------------


def _sha256_digest(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _write_v1_fixture(workspace: Path, *, with_artifact: bool = True) -> bytes:
    """写入 v1 Context 与可选 artifact，返回原始 Context 字节。"""
    paths = _layout_paths(workspace)
    paths["run_context"].parent.mkdir(parents=True, exist_ok=True)
    raw = V1_FIXTURE.read_bytes()
    paths["run_context"].write_bytes(raw)
    if with_artifact:
        art = workspace / ".climate" / "data" / RUN_ID / "sample.csv"
        art.parent.mkdir(parents=True, exist_ok=True)
        art.write_bytes(SAMPLE_CSV)
    return raw


def _marker_path(workspace: Path, transaction_id: str) -> Path:
    return workspace / ".climate" / "transactions" / f"active-run-{transaction_id}.json"


def _write_marker(
    workspace: Path,
    *,
    transaction_id: str,
    old_active_run_id: str | None,
    new_active_run_id: str,
    run_context_written: bool,
    index_written: bool,
) -> Path:
    path = _marker_path(workspace, transaction_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "transaction_id": transaction_id,
        "old_active_run_id": old_active_run_id,
        "new_active_run_id": new_active_run_id,
        "run_context_written": run_context_written,
        "index_written": index_written,
    }
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


def test_v1_migration_is_backed_up_and_idempotent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """MIG-001：备份原始字节、补 sequence/sha256、幂等；备份失败中止。"""
    workspace = (tmp_path / "ws").resolve()
    workspace.mkdir()
    repo = ContextRepository(workspace)
    repo.ensure_layout()
    original = _write_v1_fixture(workspace, with_artifact=True)
    paths = _layout_paths(workspace)

    # load_run 对 v1 必须 SCHEMA_UNSUPPORTED，且不改文件
    with pytest.raises(ClimateError) as unsupported:
        repo.load_run(RUN_ID)
    assert unsupported.value.code == "CLIMATE_SCHEMA_UNSUPPORTED"
    assert paths["run_context"].read_bytes() == original

    migrated = repo.migrate_run_to_v2(RUN_ID)
    assert migrated.schema_version == 2
    assert [e.sequence for e in migrated.events] == [1, 2, 3, 4]
    expected_sha = _sha256_digest(SAMPLE_CSV)
    assert migrated.artifacts[0].sha256 == expected_sha
    assert migrated.events[-1].type == "migration_completed"
    assert any(e.type == "migration_completed" for e in migrated.events)

    backups = list(paths["backups"].glob(f"{RUN_ID}-context-v1-*.json"))
    assert len(backups) == 1
    assert backups[0].read_bytes() == original

    # 磁盘已是 v2
    on_disk = json.loads(paths["run_context"].read_text(encoding="utf-8"))
    assert on_disk["schema_version"] == 2
    assert on_disk["artifacts"][0]["sha256"] == expected_sha

    # 幂等：再次迁移不新增破坏性备份、结果一致
    again = repo.migrate_run_to_v2(RUN_ID)
    assert again.model_dump(mode="json") == migrated.model_dump(mode="json")
    assert len(list(paths["backups"].glob(f"{RUN_ID}-context-v1-*.json"))) == 1

    # artifact 缺失 → MIGRATION_FAILED，原文件不变
    workspace2 = (tmp_path / "ws2").resolve()
    workspace2.mkdir()
    repo2 = ContextRepository(workspace2)
    repo2.ensure_layout()
    missing_raw = _write_v1_fixture(workspace2, with_artifact=False)
    ctx2 = workspace2 / ".climate" / "runs" / RUN_ID / "context.json"
    with pytest.raises(ClimateError) as missing:
        repo2.migrate_run_to_v2(RUN_ID)
    assert missing.value.code == "CLIMATE_MIGRATION_FAILED"
    assert ctx2.read_bytes() == missing_raw
    assert list((workspace2 / ".climate" / "backups").glob("*.json")) == []

    # 备份失败中止，原文件不变
    workspace3 = (tmp_path / "ws3").resolve()
    workspace3.mkdir()
    repo3 = ContextRepository(workspace3)
    repo3.ensure_layout()
    boom_raw = _write_v1_fixture(workspace3, with_artifact=True)
    ctx3 = workspace3 / ".climate" / "runs" / RUN_ID / "context.json"
    real_atomic = fs_mod.atomic_write_text

    def fail_backup(path: Any, data: str, **kwargs: Any) -> None:
        if "backups" in str(path).replace("\\", "/"):
            raise OSError("simulated backup failure")
        return real_atomic(path, data, **kwargs)

    monkeypatch.setattr("openharness.climate.repository.atomic_write_text", fail_backup)
    with pytest.raises(ClimateError) as backup_fail:
        repo3.migrate_run_to_v2(RUN_ID)
    assert backup_fail.value.code == "CLIMATE_MIGRATION_FAILED"
    assert ctx3.read_bytes() == boom_raw


def test_corrupt_or_unwritable_context_is_not_overwritten(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """REC-001：损坏原字节不变；不可写时不二次记录 last_error。"""
    workspace = (tmp_path / "ws").resolve()
    workspace.mkdir()
    repo = ContextRepository(workspace)
    repo.ensure_layout()
    paths = _layout_paths(workspace)
    paths["run_context"].parent.mkdir(parents=True, exist_ok=True)
    paths["run_context"].write_text("{corrupt-json", encoding="utf-8")
    corrupt = paths["run_context"].read_bytes()

    with pytest.raises(ClimateError) as exc_info:
        repo.load_run(RUN_ID)
    assert exc_info.value.code == "CLIMATE_CONTEXT_CORRUPT"
    assert paths["run_context"].read_bytes() == corrupt

    # 恢复路径遇到损坏 Context 也不得覆盖
    tx = "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee"
    _write_marker(
        workspace,
        transaction_id=tx,
        old_active_run_id=None,
        new_active_run_id=RUN_ID,
        run_context_written=True,
        index_written=False,
    )
    repo.recover_active_run_transactions()
    assert paths["run_context"].read_bytes() == corrupt

    # 不可写：记录 last_error 失败后不得二次写入
    good = (tmp_path / "ws-good").resolve()
    good.mkdir()
    repo_g = ContextRepository(good)
    repo_g.ensure_layout()
    repo_g.save_run(_run(), expected_version=None)
    ctx_path = good / ".climate" / "runs" / RUN_ID / "context.json"
    before = ctx_path.read_bytes()
    write_calls: list[Path] = []
    real_atomic = fs_mod.atomic_write_text

    def counting_fail(path: Any, data: str, **kwargs: Any) -> None:
        write_calls.append(Path(path))
        raise OSError("simulated unwritable context")

    monkeypatch.setattr("openharness.climate.repository.atomic_write_text", counting_fail)
    with pytest.raises(ClimateError) as write_err:
        repo_g.record_last_error(
            RUN_ID,
            {
                "code": "CLIMATE_INTERRUPTED",
                "message": "中断",
                "retryable": True,
                "details": {},
            },
            expected_version=1,
        )
    assert write_err.value.code == "CLIMATE_WRITE_FAILED"
    # 仅一次写尝试：不得为记录“写失败”再写 last_error
    assert len(write_calls) == 1
    assert Path(write_calls[0]) == ctx_path
    # monkeypatch 阻止了写入，原文件应仍在（若原子写未替换）
    # 恢复真实 atomic 后确认未改
    monkeypatch.setattr("openharness.climate.repository.atomic_write_text", real_atomic)
    assert ctx_path.read_bytes() == before


@pytest.mark.parametrize(
    "fault_point",
    [
        "before_marker",
        "marker_only",
        "context_written",
        "index_written",
        "marker_delete_failed",
    ],
)
def test_active_run_transaction_recovers_each_fault_point(
    tmp_path: Path, fault_point: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """REC-002：每个故障点可恢复且幂等，最终最多一个 active run。"""
    workspace = (tmp_path / "ws").resolve()
    workspace.mkdir()
    repo = ContextRepository(workspace)
    repo.ensure_layout()

    old_id: str | None = None
    if fault_point != "before_marker":
        # 预先存在一个旧 active，便于回滚断言
        old_id = RUN_ID_B
        repo.save_run(_run(run_id=old_id, objective="old"), expected_version=None)
        repo.save_index(
            _index(version=1, active_run_id=old_id, run_ids=[old_id]),
            expected_version=None,
        )

    tx = "bbbbbbbb-cccc-4ddd-8eee-ffffffffffff"
    paths = _layout_paths(workspace)
    new_ctx = _run(run_id=RUN_ID, objective="new")

    if fault_point == "before_marker":
        # 无 marker、无新 Context：恢复应为空操作
        pass
    elif fault_point == "marker_only":
        _write_marker(
            workspace,
            transaction_id=tx,
            old_active_run_id=old_id,
            new_active_run_id=RUN_ID,
            run_context_written=False,
            index_written=False,
        )
    elif fault_point == "context_written":
        paths["run_context"].parent.mkdir(parents=True, exist_ok=True)
        paths["run_context"].write_text(
            json.dumps(new_ctx.model_dump(mode="json"), ensure_ascii=False, indent=2, sort_keys=True)
            + "\n",
            encoding="utf-8",
        )
        _write_marker(
            workspace,
            transaction_id=tx,
            old_active_run_id=old_id,
            new_active_run_id=RUN_ID,
            run_context_written=True,
            index_written=False,
        )
    elif fault_point == "index_written":
        paths["run_context"].parent.mkdir(parents=True, exist_ok=True)
        paths["run_context"].write_text(
            json.dumps(new_ctx.model_dump(mode="json"), ensure_ascii=False, indent=2, sort_keys=True)
            + "\n",
            encoding="utf-8",
        )
        run_ids = [old_id, RUN_ID] if old_id else [RUN_ID]
        # 过滤 None
        run_ids = [r for r in run_ids if r is not None]
        index = _index(version=1, active_run_id=RUN_ID, run_ids=run_ids)
        if old_id:
            # 覆盖已有 index：需按 version 更新
            current = repo.load_index()
            repo.save_index(
                current.model_copy(
                    update={
                        "active_run_id": RUN_ID,
                        "run_ids": list(dict.fromkeys([*current.run_ids, RUN_ID])),
                        "updated_at": "2026-08-22T15:00:00Z",
                    }
                ),
                expected_version=current.version,
            )
        else:
            repo.save_index(index, expected_version=None)
        _write_marker(
            workspace,
            transaction_id=tx,
            old_active_run_id=old_id,
            new_active_run_id=RUN_ID,
            run_context_written=True,
            index_written=True,
        )
    elif fault_point == "marker_delete_failed":
        # 先完整走 create_and_activate，但删除 marker 失败
        delete_calls = {"n": 0}
        real_unlink = Path.unlink

        def flaky_unlink(self: Path, *args: Any, **kwargs: Any) -> None:
            text = str(self).replace("\\", "/")
            if "active-run-" in text and text.endswith(".json"):
                delete_calls["n"] += 1
                if delete_calls["n"] == 1:
                    raise OSError("simulated marker delete failure")
            return real_unlink(self, *args, **kwargs)

        monkeypatch.setattr(Path, "unlink", flaky_unlink)
        if old_id is None:
            repo.save_index(_index(), expected_version=None)
        repo.create_and_activate_run(new_ctx)
        # marker 应仍在
        markers = list(paths["transactions"].glob("active-run-*.json"))
        assert len(markers) == 1

    # 重复恢复两次
    for _ in range(2):
        repo.recover_active_run_transactions()

    markers_after = list(paths["transactions"].glob("active-run-*.json"))
    assert markers_after == []

    if fault_point == "before_marker":
        # 无 index 时 recover 不应捏造 active
        if paths["index"].is_file():
            idx = repo.load_index()
            assert idx.active_run_id in (None, old_id)
        return

    if fault_point == "marker_only":
        # 回滚到旧 active；新 Context 不存在 → 不得激活 RUN_ID
        idx = repo.load_index()
        assert idx.active_run_id == old_id
        assert RUN_ID not in idx.run_ids or idx.active_run_id != RUN_ID
        with pytest.raises(ClimateError) as missing:
            repo.load_run(RUN_ID)
        assert missing.value.code == "CLIMATE_RUN_NOT_FOUND"
        return

    # context_written / index_written / marker_delete_failed：应完成到新 active
    idx = repo.load_index()
    assert idx.active_run_id == RUN_ID
    assert idx.run_ids.count(RUN_ID) == 1
    loaded = repo.load_run(RUN_ID)
    assert loaded.run_id == RUN_ID
    # 至多一个 active
    assert idx.active_run_id is not None


def test_orphan_requires_explicit_resume(tmp_path: Path) -> None:
    """REC-003：orphan 只列出不自动激活；resume 仅激活指定有效 orphan。"""
    workspace = (tmp_path / "ws").resolve()
    workspace.mkdir()
    repo = ContextRepository(workspace)
    repo.ensure_layout()

    # active = RUN_ID；orphan = RUN_ID_B（磁盘有效但 index 未引用）
    repo.save_run(_run(run_id=RUN_ID, objective="active"), expected_version=None)
    repo.save_run(_run(run_id=RUN_ID_B, objective="orphan"), expected_version=None)
    repo.save_index(
        _index(active_run_id=RUN_ID, run_ids=[RUN_ID]),
        expected_version=None,
    )

    repo.recover_active_run_transactions()
    orphans = repo.list_orphan_run_ids()
    assert orphans == [RUN_ID_B]
    assert repo.load_index().active_run_id == RUN_ID

    # 损坏 orphan 不得被 resume
    bad_id = "2a0a8ad6-b5f4-4a49-af44-b3c40ac1b536"
    bad_path = workspace / ".climate" / "runs" / bad_id / "context.json"
    bad_path.parent.mkdir(parents=True, exist_ok=True)
    bad_path.write_text("{bad", encoding="utf-8")
    bad_bytes = bad_path.read_bytes()

    with pytest.raises(ClimateError) as corrupt_resume:
        repo.resume_orphan(bad_id)
    assert corrupt_resume.value.code in {
        "CLIMATE_CONTEXT_CORRUPT",
        "CLIMATE_RUN_NOT_FOUND",
        "CLIMATE_INVALID_INPUT",
    }
    assert bad_path.read_bytes() == bad_bytes
    assert repo.load_index().active_run_id == RUN_ID

    # 不存在
    missing_id = "3b1b9be7-c6e5-4bfa-9b55-c4d51bd2c647"
    with pytest.raises(ClimateError) as missing:
        repo.resume_orphan(missing_id)
    assert missing.value.code == "CLIMATE_RUN_NOT_FOUND"

    # 已是 active
    with pytest.raises(ClimateError) as already:
        repo.resume_orphan(RUN_ID)
    assert already.value.code in {"CLIMATE_INVALID_INPUT", "CLIMATE_RUN_EXISTS"}
    assert repo.load_index().active_run_id == RUN_ID

    # 显式 resume 有效 orphan
    resumed = repo.resume_orphan(RUN_ID_B)
    assert resumed.run_id == RUN_ID_B
    idx = repo.load_index()
    assert idx.active_run_id == RUN_ID_B
    assert RUN_ID_B in idx.run_ids
    assert RUN_ID in idx.run_ids  # 旧 run 仍在列表中
    assert repo.list_orphan_run_ids() == []
