"""CI Python 3.10 没有 datetime.UTC（3.11 才加入）。"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
_SCAN_DIRS = (
    ROOT / "src" / "openharness" / "climate",
    ROOT / "evals" / "climate",
    ROOT / "tests" / "test_climate",
)
_FORBIDDEN = "from datetime import UTC"


def test_climate_and_evals_do_not_import_datetime_utc() -> None:
    """收集阶段不得 from datetime import UTC，否则 CI 3.10 直接 ERROR。"""
    offenders: list[str] = []
    for directory in _SCAN_DIRS:
        for path in directory.rglob("*.py"):
            if path.name == "test_py310_datetime.py":
                continue
            text = path.read_text(encoding="utf-8")
            if _FORBIDDEN in text:
                offenders.append(path.relative_to(ROOT).as_posix())
    assert offenders == []
