"""Climate Context Repository：原子持久化、锁、迁移与 active-run 恢复。"""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from collections.abc import Callable, Iterator
from contextlib import contextmanager, suppress
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, TypeVar

from pydantic import BaseModel, ConfigDict, ValidationError

from openharness.climate.errors import ClimateError, climate_error
from openharness.climate.models import (
    ClimateErrorObject,
    RunContext,
    WorkspaceIndex,
    dumps_climate_json,
    loads_run_context,
    loads_workspace_index,
)
from openharness.climate.paths import WriteZone, resolve_workspace_path, validate_write_zone
from openharness.utils.file_lock import SwarmLockError, exclusive_file_lock
from openharness.utils.fs import atomic_write_text

T = TypeVar("T", bound=BaseModel)

_INDEX_SCHEMA = 1
_RUN_SCHEMA = 2
_RUN_SCHEMA_V1 = 1
_UUID_V4 = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
)
_MARKER_NAME = re.compile(
    r"^active-run-([0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12})\.json$"
)


class ActiveRunMarker(BaseModel):
    """active-run WAL marker（transactions/active-run-<id>.json）。"""

    model_config = ConfigDict(extra="forbid")

    transaction_id: str
    old_active_run_id: str | None = None
    new_active_run_id: str
    run_context_written: bool = False
    index_written: bool = False


class ContextRepository:
    """以 `.climate/` 下 JSON 为唯一权威业务状态的仓库。"""

    def __init__(self, workspace: Path) -> None:
        try:
            self._workspace = workspace.resolve()
        except OSError as exc:
            raise climate_error(
                "CLIMATE_INVALID_PATH",
                "无法解析 workspace 真实路径",
                workspace=workspace,
            ) from exc

    @property
    def workspace(self) -> Path:
        return self._workspace

    def ensure_layout(self) -> None:
        """创建固定 `.climate/` 目录布局（不含业务 JSON）。"""
        root = self._workspace / ".climate"
        for name in ("runs", "data", "output", "locks", "transactions", "backups"):
            (root / name).mkdir(parents=True, exist_ok=True)

    def load_index(self) -> WorkspaceIndex:
        """读取 workspace index；失败不修改文件。"""
        path = self._index_path()
        return self._load_model(
            path,
            kind="index",
            expected_schema=_INDEX_SCHEMA,
            loader=loads_workspace_index,
            not_found_as_run=False,
        )

    def save_index(
        self,
        index: WorkspaceIndex,
        *,
        expected_version: int | None,
    ) -> WorkspaceIndex:
        """原子保存 index；expected_version=None 表示首次创建。"""
        path = self._index_path()
        validate_write_zone(self._workspace, path, WriteZone.STATE)
        with self._lock(self._workspace_lock_path()):
            return self._save_model(
                path,
                index,
                expected_version=expected_version,
                kind="index",
                expected_schema=_INDEX_SCHEMA,
                loader=loads_workspace_index,
            )

    def load_run(self, run_id: str) -> RunContext:
        """读取 run Context；区分不存在 / 损坏 / schema 不支持。"""
        path = self._run_context_path(run_id)
        return self._load_model(
            path,
            kind="run",
            expected_schema=_RUN_SCHEMA,
            loader=loads_run_context,
            not_found_as_run=True,
            run_id=run_id,
        )

    def save_run(
        self,
        context: RunContext,
        *,
        expected_version: int | None,
    ) -> RunContext:
        """原子保存 run Context；仅持有 run lock（不改变 index）。"""
        path = self._run_context_path(context.run_id)
        validate_write_zone(self._workspace, path, WriteZone.STATE, run_id=context.run_id)
        with self._lock(self._run_lock_path(context.run_id)):
            return self._save_model(
                path,
                context,
                expected_version=expected_version,
                kind="run",
                expected_schema=_RUN_SCHEMA,
                loader=loads_run_context,
            )

    def migrate_run_to_v2(self, run_id: str) -> RunContext:
        """MIG-001：v1→v2 单步迁移；先原子备份原始字节，再写 v2。"""
        if not _UUID_V4.fullmatch(run_id):
            raise climate_error(
                "CLIMATE_INVALID_INPUT",
                "run_id 必须是规范小写 UUID v4",
                details={"run_id": run_id},
                workspace=self._workspace,
            )
        path = self._run_context_path(run_id)
        validate_write_zone(self._workspace, path, WriteZone.STATE, run_id=run_id)
        with self._lock(self._run_lock_path(run_id)):
            if not path.is_file():
                raise climate_error(
                    "CLIMATE_RUN_NOT_FOUND",
                    "run 不存在",
                    details={"run_id": run_id},
                    workspace=self._workspace,
                )
            try:
                original = path.read_bytes()
            except OSError as exc:
                raise climate_error(
                    "CLIMATE_CONTEXT_CORRUPT",
                    "无法读取 run",
                    details={"reason": "invalid_semantics", "field": "run"},
                    workspace=self._workspace,
                ) from exc

            try:
                raw = json.loads(original.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise climate_error(
                    "CLIMATE_CONTEXT_CORRUPT",
                    "run JSON 无效",
                    details={"reason": "invalid_json", "field": "run"},
                    workspace=self._workspace,
                ) from exc

            if not isinstance(raw, dict):
                raise climate_error(
                    "CLIMATE_CONTEXT_CORRUPT",
                    "run 根节点必须是对象",
                    details={"reason": "invalid_semantics", "field": "run"},
                    workspace=self._workspace,
                )

            schema_version = raw.get("schema_version")
            if schema_version == _RUN_SCHEMA:
                try:
                    return loads_run_context(original.decode("utf-8"))
                except (ValidationError, ValueError, TypeError) as exc:
                    raise climate_error(
                        "CLIMATE_CONTEXT_CORRUPT",
                        "run 语义无效",
                        details={"reason": "invalid_semantics", "field": "run"},
                        workspace=self._workspace,
                    ) from exc

            if schema_version != _RUN_SCHEMA_V1:
                raise climate_error(
                    "CLIMATE_SCHEMA_UNSUPPORTED",
                    "不支持的 run schema 版本",
                    details={
                        "schema_version": schema_version
                        if isinstance(schema_version, int)
                        else None,
                        "field": "run",
                    },
                    workspace=self._workspace,
                )

            try:
                migrated = self._build_v2_from_v1(raw, original_bytes=original)
            except ClimateMigrationAbort as exc:
                raise exc.error from None

            stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
            backup_rel = f".climate/backups/{run_id}-context-v1-{stamp}.json"
            backup_path = resolve_workspace_path(self._workspace, backup_rel)
            validate_write_zone(self._workspace, backup_path, WriteZone.STATE)
            try:
                atomic_write_text(backup_path, original.decode("utf-8"))
            except OSError as exc:
                raise climate_error(
                    "CLIMATE_MIGRATION_FAILED",
                    "迁移备份失败",
                    details={"reason": type(exc).__name__, "field": "backup"},
                    workspace=self._workspace,
                ) from exc

            payload = dumps_climate_json(migrated)
            try:
                atomic_write_text(path, payload)
            except OSError as exc:
                raise climate_error(
                    "CLIMATE_MIGRATION_FAILED",
                    "写入迁移后 Context 失败",
                    details={"reason": type(exc).__name__, "field": "run"},
                    workspace=self._workspace,
                ) from exc
            return migrated

    def record_last_error(
        self,
        run_id: str,
        error: dict[str, Any] | ClimateErrorObject,
        *,
        expected_version: int,
    ) -> RunContext:
        """写入 last_error；写失败直接返回原始持久化错误，不二次记录。"""
        if isinstance(error, ClimateErrorObject):
            err_obj = error
        else:
            try:
                err_obj = ClimateErrorObject.model_validate(error)
            except (ValidationError, ValueError, TypeError) as exc:
                raise climate_error(
                    "CLIMATE_INVALID_INPUT",
                    "last_error 结构无效",
                    details={"field": "last_error"},
                    workspace=self._workspace,
                ) from exc

        current = self.load_run(run_id)
        updated = current.model_copy(
            update={
                "last_error": err_obj,
                "updated_at": _utc_now(),
            }
        )
        # 单次 save；失败不递归写 last_error
        return self.save_run(updated, expected_version=expected_version)

    def create_and_activate_run(self, context: RunContext) -> RunContext:
        """通过 active-run WAL 创建 Context 并切换 active run。"""
        self.ensure_layout()
        self.recover_active_run_transactions()
        run_id = context.run_id
        with self._ordered_locks(run_id):
            if self._run_context_path(run_id).is_file():
                raise climate_error(
                    "CLIMATE_RUN_EXISTS",
                    "run_id 已存在",
                    details={"run_id": run_id},
                    workspace=self._workspace,
                )
            old_active = self._read_active_run_id_unlocked()
            return self._commit_active_run_transaction(
                old_active_run_id=old_active,
                new_active_run_id=run_id,
                write_context=context,
            )

    def resume_orphan(self, resume_run_id: str) -> RunContext:
        """REC-003：仅激活指定且有效的 orphan。"""
        if not _UUID_V4.fullmatch(resume_run_id):
            raise climate_error(
                "CLIMATE_INVALID_INPUT",
                "resume_run_id 必须是规范小写 UUID v4",
                details={"run_id": resume_run_id},
                workspace=self._workspace,
            )
        self.ensure_layout()
        self.recover_active_run_transactions()
        with self._ordered_locks(resume_run_id):
            index = self._load_index_or_empty_unlocked()
            if index.active_run_id == resume_run_id:
                raise climate_error(
                    "CLIMATE_INVALID_INPUT",
                    "目标 run 已是 active",
                    details={"run_id": resume_run_id, "status": "active"},
                    workspace=self._workspace,
                )
            if resume_run_id in index.run_ids:
                raise climate_error(
                    "CLIMATE_INVALID_INPUT",
                    "目标 run 已在 index 中，不是 orphan",
                    details={"run_id": resume_run_id, "status": "indexed"},
                    workspace=self._workspace,
                )
            # 必须是有效 v2 Context
            context = self._load_model(
                self._run_context_path(resume_run_id),
                kind="run",
                expected_schema=_RUN_SCHEMA,
                loader=loads_run_context,
                not_found_as_run=True,
                run_id=resume_run_id,
            )
            self._commit_active_run_transaction(
                old_active_run_id=index.active_run_id,
                new_active_run_id=resume_run_id,
                write_context=None,
            )
            return context

    def list_orphan_run_ids(self) -> list[str]:
        """列出 index 未引用但磁盘上有效的 run（不自动激活）。"""
        self.ensure_layout()
        with self._lock(self._workspace_lock_path()):
            return self._list_orphan_run_ids_unlocked()

    def recover_active_run_transactions(self) -> None:
        """REC-002：按文件事实完成或回滚未完成的 active-run WAL。"""
        self.ensure_layout()
        with self._lock(self._workspace_lock_path()):
            self._recover_under_workspace_lock()

    # --- 路径 ---

    def _index_path(self) -> Path:
        return resolve_workspace_path(self._workspace, ".climate/index.json")

    def _run_context_path(self, run_id: str) -> Path:
        return resolve_workspace_path(
            self._workspace, f".climate/runs/{run_id}/context.json"
        )

    def _workspace_lock_path(self) -> Path:
        return resolve_workspace_path(self._workspace, ".climate/locks/workspace.lock")

    def _run_lock_path(self, run_id: str) -> Path:
        return resolve_workspace_path(self._workspace, f".climate/locks/{run_id}.lock")

    def _transactions_dir(self) -> Path:
        return resolve_workspace_path(self._workspace, ".climate/transactions")

    def _marker_path(self, transaction_id: str) -> Path:
        return resolve_workspace_path(
            self._workspace, f".climate/transactions/active-run-{transaction_id}.json"
        )

    # --- 锁 ---

    @contextmanager
    def _lock(self, lock_path: Path) -> Iterator[None]:
        try:
            with exclusive_file_lock(lock_path):
                yield
        except SwarmLockError as exc:
            raise climate_error(
                "CLIMATE_LOCK_FAILED",
                "无法获取 Climate 状态锁",
                details={"reason": type(exc).__name__},
                workspace=self._workspace,
            ) from exc

    @contextmanager
    def _ordered_locks(self, run_id: str) -> Iterator[None]:
        """workspace → run 固定锁序。"""
        with (
            self._lock(self._workspace_lock_path()),
            self._lock(self._run_lock_path(run_id)),
        ):
            yield

    # --- 加载 / 保存 ---

    def _load_model(
        self,
        path: Path,
        *,
        kind: str,
        expected_schema: int,
        loader: Callable[[str], T],
        not_found_as_run: bool,
        run_id: str | None = None,
    ) -> T:
        if not path.is_file():
            if not_found_as_run:
                raise climate_error(
                    "CLIMATE_RUN_NOT_FOUND",
                    "run 不存在",
                    details={"run_id": run_id} if run_id else None,
                    workspace=self._workspace,
                )
            raise climate_error(
                "CLIMATE_CONTEXT_CORRUPT",
                f"{kind} 不存在或不可读",
                details={"reason": "invalid_semantics", "field": kind},
                workspace=self._workspace,
            )

        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            raise climate_error(
                "CLIMATE_CONTEXT_CORRUPT",
                f"无法读取 {kind}",
                details={"reason": "invalid_semantics", "field": kind},
                workspace=self._workspace,
            ) from exc

        try:
            raw = json.loads(text)
        except json.JSONDecodeError as exc:
            raise climate_error(
                "CLIMATE_CONTEXT_CORRUPT",
                f"{kind} JSON 无效",
                details={"reason": "invalid_json", "field": kind},
                workspace=self._workspace,
            ) from exc

        if not isinstance(raw, dict):
            raise climate_error(
                "CLIMATE_CONTEXT_CORRUPT",
                f"{kind} 根节点必须是对象",
                details={"reason": "invalid_semantics", "field": kind},
                workspace=self._workspace,
            )

        schema_version = raw.get("schema_version")
        if schema_version != expected_schema:
            raise climate_error(
                "CLIMATE_SCHEMA_UNSUPPORTED",
                f"不支持的 {kind} schema 版本",
                details={
                    "schema_version": schema_version
                    if isinstance(schema_version, int)
                    else None,
                    "field": kind,
                },
                workspace=self._workspace,
            )

        try:
            return loader(text)
        except (ValidationError, ValueError, TypeError) as exc:
            raise climate_error(
                "CLIMATE_CONTEXT_CORRUPT",
                f"{kind} 语义无效",
                details={"reason": "invalid_semantics", "field": kind},
                workspace=self._workspace,
            ) from exc

    def _save_model(
        self,
        path: Path,
        model: T,
        *,
        expected_version: int | None,
        kind: str,
        expected_schema: int,
        loader: Callable[[str], T],
    ) -> T:
        exists = path.is_file()
        if expected_version is None:
            if exists:
                raise climate_error(
                    "CLIMATE_VERSION_CONFLICT",
                    f"{kind} 已存在，无法以创建方式写入",
                    details={"field": kind},
                    workspace=self._workspace,
                )
            to_write: T = model
        else:
            if not exists:
                raise climate_error(
                    "CLIMATE_VERSION_CONFLICT",
                    f"{kind} 不存在，无法按 expected_version 更新",
                    details={
                        "expected_version": expected_version,
                        "field": kind,
                    },
                    workspace=self._workspace,
                )
            current = self._load_model(
                path,
                kind=kind,
                expected_schema=expected_schema,
                loader=loader,
                not_found_as_run=False,
            )
            actual_version = current.version
            if actual_version != expected_version:
                raise climate_error(
                    "CLIMATE_VERSION_CONFLICT",
                    "Context 版本冲突",
                    details={
                        "expected_version": expected_version,
                        "actual_version": actual_version,
                        "field": kind,
                    },
                    workspace=self._workspace,
                )
            to_write = model.model_copy(update={"version": expected_version + 1})

        payload = dumps_climate_json(to_write)
        try:
            atomic_write_text(path, payload)
        except OSError as exc:
            raise climate_error(
                "CLIMATE_WRITE_FAILED",
                f"原子写入 {kind} 失败",
                details={"field": kind, "reason": type(exc).__name__},
                workspace=self._workspace,
            ) from exc

        return to_write

    def _save_model_unlocked(
        self,
        path: Path,
        model: T,
        *,
        expected_version: int | None,
        kind: str,
        expected_schema: int,
        loader: Callable[[str], T],
    ) -> T:
        """调用方已持有相应锁时使用。"""
        return self._save_model(
            path,
            model,
            expected_version=expected_version,
            kind=kind,
            expected_schema=expected_schema,
            loader=loader,
        )

    # --- 迁移 ---

    def _build_v2_from_v1(
        self, raw: dict[str, Any], *, original_bytes: bytes
    ) -> RunContext:
        del original_bytes  # 仅用于调用侧备份；此处不修改
        data = dict(raw)
        data["schema_version"] = _RUN_SCHEMA

        events_in = data.get("events")
        if not isinstance(events_in, list):
            raise ClimateMigrationAbort(
                climate_error(
                    "CLIMATE_MIGRATION_FAILED",
                    "v1 events 无效",
                    details={"reason": "invalid_semantics", "field": "events"},
                    workspace=self._workspace,
                )
            )
        new_events: list[dict[str, Any]] = []
        for index, event in enumerate(events_in, start=1):
            if not isinstance(event, dict):
                raise ClimateMigrationAbort(
                    climate_error(
                        "CLIMATE_MIGRATION_FAILED",
                        "v1 event 无效",
                        details={"reason": "invalid_semantics", "field": "events"},
                        workspace=self._workspace,
                    )
                )
            item = dict(event)
            item["sequence"] = index
            new_events.append(item)

        artifacts_in = data.get("artifacts")
        if not isinstance(artifacts_in, list):
            raise ClimateMigrationAbort(
                climate_error(
                    "CLIMATE_MIGRATION_FAILED",
                    "v1 artifacts 无效",
                    details={"reason": "invalid_semantics", "field": "artifacts"},
                    workspace=self._workspace,
                )
            )
        new_artifacts: list[dict[str, Any]] = []
        for art in artifacts_in:
            if not isinstance(art, dict):
                raise ClimateMigrationAbort(
                    climate_error(
                        "CLIMATE_MIGRATION_FAILED",
                        "v1 artifact 无效",
                        details={"reason": "invalid_semantics", "field": "artifacts"},
                        workspace=self._workspace,
                    )
                )
            item = dict(art)
            rel = item.get("path")
            if not isinstance(rel, str):
                raise ClimateMigrationAbort(
                    climate_error(
                        "CLIMATE_MIGRATION_FAILED",
                        "artifact 路径无效",
                        details={"reason": "invalid_semantics", "field": "path"},
                        workspace=self._workspace,
                    )
                )
            try:
                art_path = resolve_workspace_path(self._workspace, rel)
            except ClimateError as exc:
                raise ClimateMigrationAbort(
                    climate_error(
                        "CLIMATE_MIGRATION_FAILED",
                        "artifact 路径不安全",
                        details={"reason": "invalid_path", "field": "path"},
                        workspace=self._workspace,
                    )
                ) from exc
            if not art_path.is_file():
                raise ClimateMigrationAbort(
                    climate_error(
                        "CLIMATE_MIGRATION_FAILED",
                        "迁移所需 artifact 缺失",
                        details={"reason": "missing_artifact", "path": rel},
                        workspace=self._workspace,
                    )
                )
            digest = hashlib.sha256(art_path.read_bytes()).hexdigest()
            item["sha256"] = f"sha256:{digest}"
            new_artifacts.append(item)

        data["events"] = new_events
        data["artifacts"] = new_artifacts
        try:
            version = int(data.get("version", 1))
        except (TypeError, ValueError):
            version = 1
        data["version"] = version + 1
        now = _utc_now()
        data["updated_at"] = now
        seq = len(new_events) + 1
        new_events.append(
            {
                "sequence": seq,
                "timestamp": now,
                "type": "migration_completed",
                "step_id": None,
                "data": {"from_schema": _RUN_SCHEMA_V1, "to_schema": _RUN_SCHEMA},
            }
        )
        data["events"] = new_events

        try:
            return RunContext.model_validate(data)
        except (ValidationError, ValueError, TypeError) as exc:
            raise ClimateMigrationAbort(
                climate_error(
                    "CLIMATE_MIGRATION_FAILED",
                    "迁移结果未通过 v2 校验",
                    details={"reason": "invalid_semantics", "field": "run"},
                    workspace=self._workspace,
                )
            ) from exc

    # --- WAL / orphan ---

    def _read_active_run_id_unlocked(self) -> str | None:
        path = self._index_path()
        if not path.is_file():
            return None
        index = self._load_model(
            path,
            kind="index",
            expected_schema=_INDEX_SCHEMA,
            loader=loads_workspace_index,
            not_found_as_run=False,
        )
        return index.active_run_id

    def _load_index_or_empty_unlocked(self) -> WorkspaceIndex:
        path = self._index_path()
        if not path.is_file():
            return WorkspaceIndex(
                schema_version=1,
                version=1,
                active_run_id=None,
                run_ids=[],
                updated_at=_utc_now(),
            )
        return self._load_model(
            path,
            kind="index",
            expected_schema=_INDEX_SCHEMA,
            loader=loads_workspace_index,
            not_found_as_run=False,
        )

    def _write_marker_unlocked(self, marker: ActiveRunMarker) -> None:
        path = self._marker_path(marker.transaction_id)
        validate_write_zone(self._workspace, path, WriteZone.STATE)
        try:
            atomic_write_text(path, dumps_climate_json(marker))
        except OSError as exc:
            raise climate_error(
                "CLIMATE_WRITE_FAILED",
                "写入 active-run marker 失败",
                details={"field": "transaction", "reason": type(exc).__name__},
                workspace=self._workspace,
            ) from exc

    def _delete_marker_unlocked(self, transaction_id: str) -> None:
        path = self._marker_path(transaction_id)
        with suppress(FileNotFoundError):
            path.unlink()

    def _try_load_valid_run_unlocked(self, run_id: str) -> RunContext | None:
        path = self._run_context_path(run_id)
        if not path.is_file():
            return None
        try:
            return self._load_model(
                path,
                kind="run",
                expected_schema=_RUN_SCHEMA,
                loader=loads_run_context,
                not_found_as_run=True,
                run_id=run_id,
            )
        except ClimateError as exc:
            if exc.code in {
                "CLIMATE_CONTEXT_CORRUPT",
                "CLIMATE_SCHEMA_UNSUPPORTED",
                "CLIMATE_RUN_NOT_FOUND",
            }:
                return None
            raise

    def _commit_active_run_transaction(
        self,
        *,
        old_active_run_id: str | None,
        new_active_run_id: str,
        write_context: RunContext | None,
    ) -> RunContext:
        """调用方已持有 workspace → run 锁。"""
        transaction_id = str(uuid.uuid4())
        marker = ActiveRunMarker(
            transaction_id=transaction_id,
            old_active_run_id=old_active_run_id,
            new_active_run_id=new_active_run_id,
            run_context_written=False,
            index_written=False,
        )
        self._write_marker_unlocked(marker)

        if write_context is not None:
            path = self._run_context_path(new_active_run_id)
            validate_write_zone(
                self._workspace, path, WriteZone.STATE, run_id=new_active_run_id
            )
            self._save_model_unlocked(
                path,
                write_context,
                expected_version=None,
                kind="run",
                expected_schema=_RUN_SCHEMA,
                loader=loads_run_context,
            )
            context = write_context
        else:
            loaded = self._try_load_valid_run_unlocked(new_active_run_id)
            if loaded is None:
                # 回滚 marker，不改变 index
                with suppress(OSError):
                    self._delete_marker_unlocked(transaction_id)
                raise climate_error(
                    "CLIMATE_CONTEXT_CORRUPT",
                    "目标 run Context 无效",
                    details={"reason": "invalid_semantics", "run_id": new_active_run_id},
                    workspace=self._workspace,
                )
            context = loaded

        marker = marker.model_copy(update={"run_context_written": True})
        self._write_marker_unlocked(marker)

        self._upsert_active_in_index_unlocked(new_active_run_id)
        marker = marker.model_copy(update={"index_written": True})
        self._write_marker_unlocked(marker)

        try:
            self._delete_marker_unlocked(transaction_id)
        except OSError:
            # 删除失败可留待恢复；事务已完成
            pass
        return context

    def _upsert_active_in_index_unlocked(self, new_active_run_id: str) -> WorkspaceIndex:
        path = self._index_path()
        validate_write_zone(self._workspace, path, WriteZone.STATE)
        now = _utc_now()
        if not path.is_file():
            index = WorkspaceIndex(
                schema_version=1,
                version=1,
                active_run_id=new_active_run_id,
                run_ids=[new_active_run_id],
                updated_at=now,
            )
            return self._save_model_unlocked(
                path,
                index,
                expected_version=None,
                kind="index",
                expected_schema=_INDEX_SCHEMA,
                loader=loads_workspace_index,
            )

        current = self._load_model(
            path,
            kind="index",
            expected_schema=_INDEX_SCHEMA,
            loader=loads_workspace_index,
            not_found_as_run=False,
        )
        run_ids = list(current.run_ids)
        if new_active_run_id not in run_ids:
            run_ids.append(new_active_run_id)
        updated = current.model_copy(
            update={
                "active_run_id": new_active_run_id,
                "run_ids": run_ids,
                "updated_at": now,
            }
        )
        return self._save_model_unlocked(
            path,
            updated,
            expected_version=current.version,
            kind="index",
            expected_schema=_INDEX_SCHEMA,
            loader=loads_workspace_index,
        )

    def _restore_active_in_index_unlocked(self, old_active_run_id: str | None) -> None:
        path = self._index_path()
        if not path.is_file():
            if old_active_run_id is None:
                return
            index = WorkspaceIndex(
                schema_version=1,
                version=1,
                active_run_id=old_active_run_id,
                run_ids=[old_active_run_id],
                updated_at=_utc_now(),
            )
            self._save_model_unlocked(
                path,
                index,
                expected_version=None,
                kind="index",
                expected_schema=_INDEX_SCHEMA,
                loader=loads_workspace_index,
            )
            return

        current = self._load_model(
            path,
            kind="index",
            expected_schema=_INDEX_SCHEMA,
            loader=loads_workspace_index,
            not_found_as_run=False,
        )
        if current.active_run_id == old_active_run_id:
            return
        run_ids = list(current.run_ids)
        if old_active_run_id is not None and old_active_run_id not in run_ids:
            run_ids.append(old_active_run_id)
        updated = current.model_copy(
            update={
                "active_run_id": old_active_run_id,
                "run_ids": run_ids,
                "updated_at": _utc_now(),
            }
        )
        self._save_model_unlocked(
            path,
            updated,
            expected_version=current.version,
            kind="index",
            expected_schema=_INDEX_SCHEMA,
            loader=loads_workspace_index,
        )

    def _list_markers_unlocked(self) -> list[tuple[Path, ActiveRunMarker]]:
        root = self._transactions_dir()
        if not root.is_dir():
            return []
        found: list[tuple[Path, ActiveRunMarker]] = []
        for path in sorted(root.glob("active-run-*.json")):
            match = _MARKER_NAME.match(path.name)
            if match is None:
                continue
            try:
                text = path.read_text(encoding="utf-8")
                marker = ActiveRunMarker.model_validate(json.loads(text))
            except (OSError, json.JSONDecodeError, ValidationError, ValueError, TypeError):
                continue
            found.append((path, marker))
        return found

    def _recover_under_workspace_lock(self) -> None:
        for path, marker in self._list_markers_unlocked():
            new_id = marker.new_active_run_id
            # 按固定锁序再取 run lock（已持有 workspace）
            with self._lock(self._run_lock_path(new_id)):
                valid = self._try_load_valid_run_unlocked(new_id)
                if valid is not None:
                    # 有效新 Context：补写 index（若需要），再删 marker
                    self._upsert_active_in_index_unlocked(new_id)
                else:
                    # 无有效 Context：恢复旧 active；不覆盖损坏文件
                    self._restore_active_in_index_unlocked(marker.old_active_run_id)
                with suppress(OSError):
                    path.unlink()

    def _list_orphan_run_ids_unlocked(self) -> list[str]:
        index = self._load_index_or_empty_unlocked()
        indexed = set(index.run_ids)
        runs_root = self._workspace / ".climate" / "runs"
        if not runs_root.is_dir():
            return []
        orphans: list[str] = []
        for child in sorted(runs_root.iterdir()):
            if not child.is_dir():
                continue
            run_id = child.name
            if not _UUID_V4.fullmatch(run_id) or run_id in indexed:
                continue
            if self._try_load_valid_run_unlocked(run_id) is not None:
                orphans.append(run_id)
        return orphans


class ClimateMigrationAbort(Exception):
    """内部：迁移逻辑失败，携带已构造的 ClimateError。"""

    def __init__(self, error: ClimateError) -> None:
        self.error = error
        super().__init__(error.message)


def _utc_now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
