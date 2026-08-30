# Day 07：G2 验收门与 G3 Eval 基础

## 今日目标

先完成 G2 只读验收；只有 G2 全部适用需求 PASS 后，才建立可执行、可失败、可追踪的 Eval 骨架。

- **SPEC 需求**：REG-001、TOOL-*、PERM-001、TEST-004、CI-001、PHASE-001；随后 EVAL-001/003（基础）
- **预计投入**：7～8 小时
- **完成标志**：G2 Gate PASS；Eval runner 能解析 scenario、执行硬断言并用退出码表达失败
- **上一天**：[Day 06](DAY_06_G2B_PLOT_REPORT_PIPELINE.md)
- **下一天**：[Day 08](DAY_08_G3_OFFLINE_EVAL_RECOVERY.md)

## 阶段边界

上午只做 G2 验收/修复。若存在 blocker/high：

1. 输出验收报告。
2. 只修报告中的 blocker/high。
3. 重新验收。
4. 未 PASS 时当天不得开始 G3。

## 上午：G2 Gate

### 1. 只读验收

```text
逐项核对 G2 的 TOOL-BASE-001、REG-001、TOOL-INIT/PLAN/ACQUIRE/INSPECT/PLOT/REPORT/READ、
PATH-003/004、IDEM-001、PERM-001、TEST-004、CI-001。
检查实现、自动化测试、真实产物、错误路径、凭证、阶段外修改和 QueryEngine diff。
只输出 blocker/high/medium/low 与 PASS/GAP，不修复。
```

### 2. 验证命令

```powershell
uv run pytest tests/test_climate -q
uv run pytest -q
uv run ruff check src tests scripts
git diff --check
git status --short
```

注意：Eval 目录尚不存在时不要提前把 `evals` 加入 Ruff 命令。

### 3. 回填 SPEC

仅对有实际测试 node ID 和通过结果的 G2 需求改 PASS。再次检查矩阵中是否存在“功能已完成但测试仍是
预定名称”的虚假状态。

## 下午：Eval Foundation

### 严格范围

建议新增：

```text
evals/__init__.py
evals/__main__.py
evals/climate/__init__.py
evals/climate/models.py
evals/climate/assertions.py
evals/climate/runner.py
evals/climate/scenarios/sample_pipeline.yaml（可先最小）
tests/test_climate/test_evals.py
.github/workflows/ci.yml（Ruff 范围加入 evals）
```

今天不做完整三场景、Hook、Skill、README，不调用真实模型或网络。

### 4. RED：Scenario/Trace/退出码（1.5 小时）

测试：

- Scenario 必填字段、mode 枚举、timeout、turns、expected sequence。
- TraceRecord 第 12 节全部字段和输入脱敏。
- hard assertion 成功/失败。
- 任一 hard assertion 失败时 CLI 非零。
- synthetic dry-run 明显标记，不能计入真实通过率。
- `--suite climate --mode real_offline|synthetic_dry_run` 参数。
- `real_agent` 可被 schema 识别，但 G3 必须明确拒绝为“G4 尚未配置”，不得伪造执行。
- 不存在 suite/scenario 返回稳定诊断。

### 5. GREEN：最小 Eval runner（1.5～2 小时）

runner 只负责：

1. 加载/校验 scenario。
2. 调用明确的执行 adapter。
3. 收集 trace。
4. 执行 hard assertions。
5. 原子输出报告并返回退出码。

synthetic adapter 只能生成 wiring 验证数据；输出必须声明不执行工具/模型。创建 `evals/` 后同步
把 CI Ruff 命令扩展为 `ruff check src tests scripts evals`。

### 6. 验证

```powershell
uv run pytest tests/test_climate/test_evals.py -q
uv run python -m evals --suite climate --mode synthetic_dry_run
uv run ruff check src tests scripts evals
git diff --check
```

## 今日主 Prompt

```text
执行 ClimWorkflow Day 07。

第一部分只做 G2 验收：
- 阅读 SPEC、DAY_07 文件。
- 运行 Climate 全量、OpenHarness 全量、Ruff。
- 按需求 ID 输出 PASS/GAP 和 blocker/high。
- 仅在我允许或验收流程要求时修 blocker/high。
- G2 未全部 PASS 时停止，不开始 G3。

第二部分仅在 G2 PASS 后执行 G3 Eval Foundation：
- 先写 Scenario、TraceRecord、hard assertion、CLI 退出码和 synthetic 标记失败测试。
- 再最小实现 evals 包和 runner。
- synthetic 不得伪装真实工具执行。

不实现 Hook/Skill/完整场景，不接网络/真实模型，不提交、不推送。
```

## 分步骤 Prompt

```text
只读验收 G2，不修复。逐项输出需求 ID→实现→测试 node ID→结果，并检查 QueryEngine 无修改。
```

```text
根据验收报告只修 blocker/high，不扩大范围；修复后重跑受影响测试和全量 Climate。
```

```text
现在只写 Eval schema、assertion 和 CLI 退出码失败测试，不实现真实 scenario。
```

```text
验收 Eval Foundation：证明 synthetic 被排除、hard assertion 能使进程失败、Trace 已脱敏。
```

## 验收清单

- [x] G2 在 G3 开始前正式 PASS。
- [x] Climate 全量 pytest 与 Ruff 通过（本机 Windows 全量 OpenHarness pytest / 未推送 GitHub CI 不作为 Climate Gate 否决）。
- [x] 7 工具、sample/local E2E、非法顺序/路径均有证据。
- [x] Eval schema 和 TraceRecord 严格校验。
- [x] hard assertion 失败产生非零退出码。
- [x] synthetic 不能计入真实成功率。
- [x] G3 的 real_agent 明确不可执行且不计入通过率。
- [x] 未实现 Day 08/09 内容。

## 风险与止损

- 全量测试时间过长不代表可跳过；可先并行定位，但 Gate 最终必须完整运行。
- 不要把“能加载 scenario”写成“scenario 真实通过”。
- 当前 Hatch wheel 不包含根目录 `evals`；G3 只承诺仓库根目录执行 `uv run python -m evals`，
  安装后入口另行评审，不在今天扩大打包范围。
- G2 blocker 占满全天时，Day 08 顺延；阶段门优先于 15 天日历。

## 日终报告

```text
Day 07：
- G2 Gate：PASS。先只读验收再修 blocker/high，G2 适用需求全部 PASS 后才开始 G3 Eval Foundation。QueryEngine 无 Climate 语义 diff；PERM-001 经现有 `_execute_tool_call` 接入。PHASE-001：G0～G2 PASS，允许进入 G3 Foundation；G3 完整场景/Hook/Skill 未完成，不得声称 Offline Engineering MVP。
    PASS：TOOL-BASE-001、REG-001、TOOL-INIT/PLAN/ACQUIRE/INSPECT/PLOT/REPORT/READ、PATH-003/004、IDEM-001、PERM-001（含 QueryEngine 路径抽取）、TEST-004、ARCH-001、SDD-001（G2）。
    GAP（不阻塞 G3 Foundation）：CI-001 远程 GitHub Actions 未推送；CTX-002 G3 compact、EVAL-002 四场景、HOOK/SKILL/DOC、G4。
- G2 blocker/high 修复：
    1. mcp 钉死 `>=1.0.0,<2`（本机曾解析到 mcp 2.1.1，缺 FastMCP，全量 pytest 收集 ERROR）。uv lock/sync 后为 1.29.1。
    2. Ruff 钉死历史 `[tool.ruff.lint] select = ["E4","E7","E9","F"]`（0.16 默认规则扩到 413 条，误报数百条，非 Climate 新增债）。
    3. PERM-001 high：新增 `tests/test_climate/test_pipeline.py::test_query_engine_path_rules_block_climate_tools_from_default_registry`，FULL_AUTO + path deny 时 `_execute_tool_call` 执行次数为 0。
    未修：本机 Windows OpenHarness 环境失败（盘符冒号、tzdata/Asia/Hong_Kong、symlink 权限、fcntl、bash vs cmd）；MCP 2.x API；Ruff 全量 413 规则。均不作为 Day 08 前置。
- 全量 pytest/Ruff：Climate `uv run pytest tests/test_climate -q` → 189 passed（`--collect-only` 同为 189）。`uv run ruff check src tests scripts evals` PASS。`git diff --check` 清洁。本机 `uv run pytest -q` 全仓库未全绿（约 23 个 OpenHarness 环境失败，不计入 Climate 回归）。GitHub 3.10/3.11 CI 未推送，无远程证据。CI-001 = PASS（本机 Climate/Ruff）；GAP（未推送 Actions）。
- SPEC 回填：页首状态、REUSE/NEW 矩阵、需求正文 PASS/GAP 与 §16 追踪矩阵已按实际 node ID 更新。EVAL-001/003、TEST-005 列出 `test_evals.py` 全部 10 个 Foundation 测试；TEST-004 补 QueryEngine 路径测试；EVAL-002、HOOK-001、MEM-001、SKILL-001、DOC-001 与 G4 项标明「预定（尚未创建）」，未把预定名标成 PASS。
- Eval schema/runner：最小 `evals/` 包（`__main__` → `evals.climate.runner`）。`--suite climate --mode synthetic_dry_run|real_offline|real_agent`；缺 suite/scenario 返回 `CLIMATE_INVALID_INPUT` exit 2。synthetic adapter 只抄 `expected_tool_sequence` 填 TraceRecord，不调用 pipeline/工具/模型。`real_offline`/`real_agent` 在加载 YAML 前以 `CLIMATE_DEPENDENCY_MISSING` 拒绝（分别指向 Day 08 / G4），不得伪造执行。报告原子写到 `evals/reports/climate-synthetic_dry_run.json`。入口约定仓库根目录 `uv run python -m evals`（Hatch wheel 不含根目录 evals）。证据：`test_scenario_requires_fields_and_mode_enum`；`test_load_sample_pipeline_yaml_roundtrip`；`test_trace_record_requires_section_12_fields_and_redacts_input`；`test_cli_accepts_suite_and_mode_flags`；`test_missing_suite_or_scenario_returns_stable_diagnostic`；`test_runner_synthetic_adapter_does_not_call_tools`；`test_real_agent_is_schema_recognized_but_g3_refuses_execution`。
- synthetic 输出标记：stdout 含 SYNTHETIC DRY-RUN / 未执行工具或模型；报告与 Trace 均 `synthetic=true`、`tools_executed=false`、`model_invoked=false`、`counts_toward_real_pass_rate=false`、`real_pass_rate=null`。Pydantic 禁止 synthetic 同时声称已执行或计入真实通过率；payload 拒绝 sk- / 主目录 / `.cdsapirc`。证据：`test_synthetic_dry_run_is_labeled_and_excluded_from_real_pass_rate`。
- hard assertion 退出码：任一 hard assertion 失败 → 仍写报告 → stdout `hard assertion failed` → exit 1。`--scenario hard_assertion_fail` 用对不上的 `tool_sequence` 固定该路径。成功 wiring（默认 `sample_pipeline`）exit 0。证据：`test_hard_assertion_success_and_failure`；`test_cli_nonzero_when_hard_assertion_fails`。
- Day 08 是否可开始：可以。G2 Gate 已正式 PASS；Eval Foundation（EVAL-001 部分、EVAL-003、TEST-005 Foundation）已落地且退出码可靠。Day 08 工作正是 EVAL-002 三场景 real_offline、MEM-001/CTX-002 多轮恢复；Hook/Skill/README 留 Day 09。未提交、未推送。
```
