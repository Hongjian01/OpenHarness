"""PRE_TOOL_USE 输出策略守卫：拒绝 write_report summary 中的固定测试标记。

由真实 HookExecutor 以 Command Hook 调用；只读环境变量，不访问网络，不调用模型。
"""

from __future__ import annotations

import json
import os

MARKER = "blocked-output-secret"


def main() -> int:
    raw = os.environ.get("OPENHARNESS_HOOK_PAYLOAD", "{}")
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        print("CLIMATE_HOOK_BLOCKED: invalid hook payload")
        return 1
    if not isinstance(payload, dict):
        print("CLIMATE_HOOK_BLOCKED: hook payload must be an object")
        return 1
    tool_input = payload.get("tool_input") or {}
    summary = ""
    if isinstance(tool_input, dict):
        summary = str(tool_input.get("summary") or "")
    if MARKER in summary:
        print("CLIMATE_HOOK_BLOCKED: output policy rejected blocked-output-secret")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
