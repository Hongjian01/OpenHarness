"""PATH-001/002/003、SEC-001、TEST-001 路径安全测试。"""

from __future__ import annotations

import json
import os
import stat
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from openharness.climate.errors import ClimateError, encode_tool_result_json, failure_envelope
from openharness.climate.paths import (
    WriteZone,
    resolve_workspace_path,
    to_workspace_relative_posix,
    validate_write_zone,
)

RUN_ID = "0e8e6eb4-93f2-4ce7-8d22-91a28fa99314"


def _expect_invalid_path(workspace: Path, relative: str) -> ClimateError:
    with pytest.raises(ClimateError) as exc_info:
        resolve_workspace_path(workspace, relative)
    err = exc_info.value
    assert err.code == "CLIMATE_INVALID_PATH"
    assert err.retryable is False
    return err


def test_accepts_safe_relative_paths(tmp_path: Path) -> None:
    """合法非空 workspace 相对路径可解析，返回位于 workspace 内的绝对 Path。"""
    workspace = (tmp_path / "ws").resolve()
    workspace.mkdir()
    nested = workspace / "data" / "nested"
    nested.mkdir(parents=True)
    (nested / "file.csv").write_text("a,b\n", encoding="utf-8")

    resolved = resolve_workspace_path(workspace, "data/nested/file.csv")
    assert resolved == (workspace / "data" / "nested" / "file.csv").resolve()
    assert resolved.is_relative_to(workspace.resolve())

    rel = to_workspace_relative_posix(workspace, resolved)
    assert rel == "data/nested/file.csv"
    assert "\\" not in rel
    assert not Path(rel).is_absolute()


@pytest.mark.parametrize(
    "unsafe",
    [
        "",
        " ",
        ".",
        "..",
        "./file.csv",
        "data/./file.csv",
        "data/../file.csv",
        "data//file.csv",
        "data/../secret",
        "~/secret",
        "~/.cdsapirc",
        "data/\x00file.csv",
        "/etc/passwd",
        "C:/Windows/System32",
        "C:\\Windows\\System32",
        "C:relative",
        "C:foo/bar",
        "//server/share/file",
        "\\\\server\\share\\file",
        "data\\file.csv",
        "data/mixed\\sep.csv",
        "mixed\\sep/file.csv",
        "CON",
        "CON.txt",
        "nul",
        "NUL",
        "COM1",
        "COM1.dat",
        "LPT9",
        "aux",
        "PRN.log",
        "data/CON/file.csv",
        "data/com1/file.csv",
    ],
    ids=lambda v: repr(v)[:40],
)
def test_rejects_unsafe_lexical_paths(tmp_path: Path, unsafe: str) -> None:
    """PATH-001：词法层拒绝绝对/穿越/UNC/保留名/混合分隔符等。"""
    workspace = (tmp_path / "ws").resolve()
    workspace.mkdir()
    _expect_invalid_path(workspace, unsafe)


def _try_make_dir_link(link: Path, target: Path) -> None:
    """创建目录 symlink；失败时在 Windows 上回退为 junction。"""
    try:
        link.symlink_to(target, target_is_directory=True)
        return
    except OSError:
        if sys.platform != "win32":
            raise
    # junction 通常不需要提升权限
    import subprocess

    completed = subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(link), str(target)],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0 or not link.exists():
        raise OSError(
            completed.stderr.strip() or completed.stdout.strip() or "mklink /J failed"
        )


def test_rejects_link_escape(tmp_path: Path) -> None:
    """PATH-002：已存在父链中的 symlink/junction 不得逃逸 workspace。"""
    workspace = (tmp_path / "ws").resolve()
    workspace.mkdir()
    outside = (tmp_path / "outside").resolve()
    outside.mkdir()
    secret = outside / "secret.txt"
    secret.write_text("top-secret", encoding="utf-8")

    link = workspace / "escape_link"
    try:
        _try_make_dir_link(link, outside)
    except OSError as exc:
        pytest.skip(f"当前平台无法创建 symlink/junction: {exc}")

    err = _expect_invalid_path(workspace, "escape_link/secret.txt")
    payload = encode_tool_result_json(failure_envelope(err))
    assert str(outside) not in payload
    assert str(secret) not in payload
    assert str(workspace) not in payload

    # 文件型 symlink 指向 workspace 外（无权限时跳过该分支，目录 junction 已覆盖核心断言）
    file_link = workspace / "file_link.csv"
    try:
        file_link.symlink_to(secret)
    except OSError:
        return
    _expect_invalid_path(workspace, "file_link.csv")


def test_rejects_when_parent_chain_cannot_be_verified(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """PATH-002：平台无法可靠验证真实路径时必须拒绝，而不是放行。"""
    workspace = (tmp_path / "ws").resolve()
    workspace.mkdir()
    (workspace / "data").mkdir()

    def boom(self: Path) -> Path:
        raise OSError("simulate resolve failure")

    monkeypatch.setattr(Path, "resolve", boom)
    _expect_invalid_path(workspace, "data/file.csv")


def test_enforces_write_zones(tmp_path: Path) -> None:
    """PATH-003：内部写入仅允许 data/output/固定状态路径。"""
    workspace = (tmp_path / "ws").resolve()
    workspace.mkdir()

    data_ok = resolve_workspace_path(
        workspace, f".climate/data/{RUN_ID}/sample.csv"
    )
    validate_write_zone(workspace, data_ok, WriteZone.DATA, run_id=RUN_ID)

    output_ok = resolve_workspace_path(
        workspace, f".climate/output/{RUN_ID}/plot.png"
    )
    validate_write_zone(workspace, output_ok, WriteZone.OUTPUT, run_id=RUN_ID)

    for relative in (
        f".climate/runs/{RUN_ID}/context.json",
        ".climate/index.json",
        ".climate/locks/workspace.lock",
        f".climate/locks/{RUN_ID}.lock",
        ".climate/transactions/active-run-aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee.json",
        f".climate/backups/{RUN_ID}-context-v1-2026-08-22T14:00:00Z.json",
    ):
        state_path = resolve_workspace_path(workspace, relative)
        validate_write_zone(workspace, state_path, WriteZone.STATE)

    # 越界写入区
    outside_data = resolve_workspace_path(workspace, "reports/out.md")
    with pytest.raises(ClimateError) as exc_info:
        validate_write_zone(workspace, outside_data, WriteZone.DATA, run_id=RUN_ID)
    assert exc_info.value.code == "CLIMATE_INVALID_PATH"

    wrong_run = resolve_workspace_path(
        workspace, ".climate/data/11111111-1111-4111-8111-111111111111/x.csv"
    )
    with pytest.raises(ClimateError) as exc_info:
        validate_write_zone(workspace, wrong_run, WriteZone.DATA, run_id=RUN_ID)
    assert exc_info.value.code == "CLIMATE_INVALID_PATH"

    # data 区不得写成 output 区路径
    with pytest.raises(ClimateError) as exc_info:
        validate_write_zone(workspace, output_ok, WriteZone.DATA, run_id=RUN_ID)
    assert exc_info.value.code == "CLIMATE_INVALID_PATH"


def test_errors_are_redacted(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """SEC-001：路径错误/envelope 不得含 home、workspace 绝对路径、token 或 traceback。"""
    home = tmp_path / "home-user"
    home.mkdir()
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.setenv("HOME", str(home))

    workspace = (tmp_path / "ws").resolve()
    workspace.mkdir()

    err = _expect_invalid_path(workspace, "../secret.txt")
    envelope = failure_envelope(err, run_id=None, context_version=None)
    text = encode_tool_result_json(envelope)
    parsed = json.loads(text)

    assert parsed["ok"] is False
    assert parsed["error"]["code"] == "CLIMATE_INVALID_PATH"
    blob = text + err.message + json.dumps(err.details, ensure_ascii=False)
    assert str(workspace) not in blob
    assert str(home) not in blob
    assert "Traceback" not in blob
    assert "cds-token" not in blob.lower()
    # details 仅相对/安全诊断
    for value in err.details.values():
        if isinstance(value, str):
            assert not os.path.isabs(value)
            assert ":" not in value[:2] or value.startswith("CLIMATE_")


@pytest.mark.skipif(sys.platform != "win32", reason="Windows drive-relative 专用")
def test_rejects_windows_drive_relative(tmp_path: Path) -> None:
    """PATH-001 补充：Windows drive-relative（当前盘相对）必须拒绝。"""
    workspace = (tmp_path / "ws").resolve()
    workspace.mkdir()
    drive = workspace.drive  # e.g. 'E:'
    _expect_invalid_path(workspace, f"{drive}relative-file.csv")


def test_local_source_must_be_regular_workspace_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """PATH-004：local 源必须是 workspace 内普通文件，拒绝目录/设备/FIFO/socket/逃逸。"""
    from openharness.climate.paths import validate_local_source_file

    workspace = (tmp_path / "ws").resolve()
    workspace.mkdir()
    source = workspace / "obs.csv"
    source.write_text("date,temperature_c\n2026-02-01,1.0\n", encoding="utf-8")

    resolved = validate_local_source_file(workspace, "obs.csv")
    assert resolved == source.resolve()
    assert resolved.is_file()
    assert resolved.is_relative_to(workspace)

    folder = workspace / "inputs"
    folder.mkdir()
    with pytest.raises(ClimateError) as dir_info:
        validate_local_source_file(workspace, "inputs")
    assert dir_info.value.code == "CLIMATE_INVALID_PATH"

    with pytest.raises(ClimateError) as dotdot_info:
        validate_local_source_file(workspace, "../secret.csv")
    assert dotdot_info.value.code == "CLIMATE_INVALID_PATH"

    with pytest.raises(ClimateError) as abs_info:
        validate_local_source_file(workspace, "/etc/passwd")
    assert abs_info.value.code == "CLIMATE_INVALID_PATH"

    with pytest.raises(ClimateError) as unc_info:
        validate_local_source_file(workspace, "//server/share/file.csv")
    assert unc_info.value.code == "CLIMATE_INVALID_PATH"

    outside = (tmp_path / "outside").resolve()
    outside.mkdir()
    (outside / "secret.csv").write_text("secret\n", encoding="utf-8")
    link = workspace / "escape_link"
    try:
        _try_make_dir_link(link, outside)
        with pytest.raises(ClimateError) as escape_info:
            validate_local_source_file(workspace, "escape_link/secret.csv")
        assert escape_info.value.code == "CLIMATE_INVALID_PATH"
    except OSError:
        pass

    file_link = workspace / "file_link.csv"
    try:
        file_link.symlink_to(source)
        with pytest.raises(ClimateError) as link_info:
            validate_local_source_file(workspace, "file_link.csv")
        assert link_info.value.code == "CLIMATE_INVALID_PATH"
    except OSError:
        pass

    original_lstat = os.lstat

    def fake_lstat(path: str | os.PathLike[str], *args: object, **kwargs: object) -> os.stat_result:
        result = original_lstat(path, *args, **kwargs)
        if Path(path).resolve() == source.resolve():
            return SimpleNamespace(  # type: ignore[return-value]
                st_mode=stat.S_IFCHR | 0o666,
                st_file_attributes=getattr(result, "st_file_attributes", 0),
            )
        return result

    monkeypatch.setattr(os, "lstat", fake_lstat)
    with pytest.raises(ClimateError) as device_info:
        validate_local_source_file(workspace, "obs.csv")
    assert device_info.value.code == "CLIMATE_INVALID_PATH"
    monkeypatch.undo()

    if sys.platform == "win32":
        return
    fifo = workspace / "pipe.csv"
    os.mkfifo(fifo)
    with pytest.raises(ClimateError) as fifo_info:
        validate_local_source_file(workspace, "pipe.csv")
    assert fifo_info.value.code == "CLIMATE_INVALID_PATH"
