# Day 08：G3 真实离线 Eval 与多轮恢复

## 今日目标

让 Eval 调用真实 Climate 工具，完成三个核心离线场景，并证明新会话可以只依赖 Context 恢复。

- **SPEC 需求**：EVAL-001、EVAL-002、EVAL-003、MEM-001、CTX-002、TEST-005
- **预计投入**：7～8 小时
- **完成标志**：sample_pipeline、cached_inspect、multiturn_recovery 全部真实执行并通过硬断言
- **上一天**：[Day 07](DAY_07_G2_GATE_G3_EVAL_FOUNDATION.md)
- **下一天**：[Day 09](DAY_09_G3_HOOK_SKILL_README.md)

## 严格范围

允许扩展 `evals/climate/`、scenario fixture、`tests/test_climate/test_evals.py`。禁止真实网络、CDS、
真实模型；今天不实现 Hook guard 或 Skill。

## 开始前检查

```powershell
git status --short --branch
uv run pytest tests/test_climate -q
uv run python -m evals --suite climate --mode synthetic_dry_run
```

确认 G2 Gate PASS，Day 07 hard assertion/退出码可靠。

## 完整开发流程

### 1. 定义真实执行边界（30 分钟）

让 Cursor 先设计、不编辑：

- `real_offline` adapter 如何构造真实 `ToolExecutionContext`、registry 和 workspace。
- scenario 如何表达 fixture 文件、工具输入、预期序列和硬断言。
- Trace 如何从真实 ToolResult/Context/artifact 收集，而非预填结果。
- timeout 和清理策略。

### 2. RED：sample_pipeline（1 小时）

硬断言至少包括：

- 7 工具按依赖顺序真实调用。
- 所有 ToolResult 成功。
- final status=completed。
- Context version 单调增长。
- dataset/plot/report 存在且 sha256 与 manifest 一致。
- 报告包含相对图链接，不含绝对 workspace。
- trace mode=`real_offline`。

### 3. RED：cached_inspect（45 分钟）

使用仓库内小型固定 CSV fixture：

- local acquire 复制而非修改源文件。
- inspect row/column/null/统计结果与 fixture 匹配。
- 不请求网络。
- 重复 inspect 同输入符合幂等契约。

### 4. RED：multiturn_recovery（1 小时）

模拟：

1. 第一会话 init/plan/acquire/inspect 后销毁内存对象。
2. 新建独立执行上下文，不传旧 tool metadata 或对话。
3. `climate_read_context` 定位 active run。
4. 继续 plot/report。
5. 最终 completed 且已有 artifact/version 未丢失。

测试必须证明恢复来源是磁盘 Context，而不是共享 Python 对象、Memory 或 synthetic trace。

### 5. GREEN：real_offline adapter 与场景（2～2.5 小时）

逐场景实现，每完成一个立即运行对应测试。Trace 中 input 必须脱敏；异常转 error_code，不写 traceback。

### 6. 验证与产物检查（1 小时）

```powershell
uv run pytest tests/test_climate/test_evals.py -q
uv run python -m evals --suite climate --mode real_offline
uv run python -m evals --suite climate --mode synthetic_dry_run
uv run pytest tests/test_climate -q
uv run ruff check src tests scripts evals
git diff --check
```

人工打开一份 Trace，核对 run_id、工具序列、错误码、耗时、final status、version、manifest 和 assertions。
确认 Eval 临时运行产物位于可忽略的临时/输出目录，不进入 Git。

## 今日主 Prompt

```text
执行 ClimWorkflow Day 08 / Phase G3：真实离线 Eval 与多轮恢复。

阅读 SPEC 第 6、11～13、15～16 节和 DAY_08_G3_OFFLINE_EVAL_RECOVERY.md。

先分别为 sample_pipeline、cached_inspect、multiturn_recovery 写失败测试和硬断言。
再实现 real_offline adapter 与三个 scenario。

强制要求：
- 调用真实 Climate Tool/Repository，不使用合成成功结果。
- multiturn 必须销毁第一会话内存并只从磁盘 Context 恢复。
- Trace 完整、脱敏、有真实耗时和 artifact 摘要。
- real_offline 全程禁网。
- synthetic 继续显著标记且不计入真实通过率。

不实现 Hook/Skill/CDS/真实模型，不提交、不推送。
```

## 分步骤 Prompt

```text
只写 sample_pipeline 硬断言测试。禁止 mock Tool.execute 或预填 artifact manifest。
```

```text
只写 multiturn_recovery 测试，明确销毁哪些对象，并加入断言证明没有继承旧 tool_metadata。
```

```text
实现 real_offline adapter；每个 trace 字段必须来自真实调用或磁盘事实，异常不得伪装成功。
```

```text
只读验收三个场景，逐个证明真实执行、禁网、硬断言、脱敏和恢复来源。不要修复。
```

## 验收清单

- [x] 三个场景均为 real_offline 真实执行。
- [x] 每个场景有硬断言，不只看进程退出码。
- [x] multiturn 不共享旧内存状态。
- [x] Trace 字段完整且无绝对路径/凭证。
- [x] synthetic 与真实统计分离。
- [x] Eval 运行产物未污染 Git。

## 风险与止损

- 禁网可通过 monkeypatch/socket guard 证明；不要仅声称没有网络调用。
- Eval runner 不应复制业务逻辑，应调用公开工具边界。
- 如果场景暴露 G2 bug，先记录需求归属并最小修复，重跑 G2 Gate 相关测试。

## 日终报告

```text
Day 08：
- sample_pipeline：PASS。real_offline 按依赖顺序真实调用 7 工具（init→plan→acquire(sample)→inspect→plot→report→read）；全部 ToolResult 成功；final status=completed；Context version 单调；dataset/plot/report 存在且 sha256 与 manifest/磁盘一致；报告含相对图链接、不含绝对 workspace；trace mode=real_offline。证据：tests/test_climate/test_evals.py::test_sample_pipeline_real_offline_hard_assertions。
- cached_inspect：PASS。仓库固定 CSV fixture（evals/climate/fixtures/cached_inspect.csv）经 local acquire 复制到 run data 区，源文件 bytes/mtime 未改；inspect row_count=3、temperature_c null_count=1/mean=12.0、precipitation_mm mean=2.0 与 fixture 匹配；二次 inspect 同输入幂等（version 不变）；全程禁网。证据：::test_cached_inspect_real_offline_hard_assertions；::test_real_offline_forbids_network。
- multiturn_recovery：PASS。第一会话 init/plan/acquire/inspect 后销毁 registry 与 ToolExecutionContext；第二会话空 metadata、不继承 eval-session-1-sentinel；climate_read_context 不传 run_id，从 index.json 定位 active run；再 plot/report；最终 completed，既有 artifact/sha256 未丢失。恢复来源 disk_context，非共享 Python 对象/Memory/synthetic。证据：::test_multiturn_recovery_destroys_memory_and_restores_from_disk。
- real_offline 命令结果：`uv run python -m evals --suite climate --mode real_offline` exit 0，real_pass_rate=1.0，三场景顺序 sample_pipeline / cached_inspect / multiturn_recovery，均 passed、synthetic=false、tools_executed=true、counts_toward_real_pass_rate=true。`uv run python -m evals --suite climate --mode synthetic_dry_run` exit 0，显著 SYNTHETIC 标记，real_pass_rate=null，不计入真实通过率。证据：::test_cli_real_offline_runs_core_scenarios；::test_synthetic_dry_run_is_labeled_and_excluded_from_real_pass_rate。
- Trace/脱敏检查：§12 字段齐全（run_id、工具序列、error_code、真实 duration_ms、final status/version、artifact_manifest、assertion_results）；input/output 脱敏；报告 JSON 无用户主目录、sk-、.cdsapirc、traceback。Eval 产物在已忽略的 evals/reports/*.json 与系统临时目录，未进 Git。
- PASS/GAP 需求：
    PASS（Day 08 范围）：EVAL-002 三核心真实离线；EVAL-001 三场景硬断言（Hook 断言仍 GAP）；TEST-005 Foundation+三场景禁网（Hook 仍 GAP）；MEM-001 多轮重启；CTX-002 G3 多轮重启；EVAL-003 保持 PASS；SDD-001 Day 08 RED→GREEN。
    GAP：HOOK-001、SKILL-001、DOC-001、CTX-002 compact/Skill、EVAL-002 Hook 场景、CI-001 未推送 GitHub Actions、G4。未声称 Offline Engineering MVP。未提交、未推送。
- 回归/Ruff：`uv run pytest tests/test_climate -q` → 195 passed（collect-only 同为 195）。`uv run ruff check src tests scripts evals` PASS。`git diff --check` 清洁。未跑全仓库 OpenHarness pytest（不计入 Climate Gate）。SPEC §16 已按 16 个 test_evals.py node ID 回填。
- Day 09 blocker：无 G2/G3 Foundation 或三场景 blocker。Day 09 可开始：pre_tool_output_guard（HOOK-001）、climate-ds Skill（SKILL-001）、README 离线演示（DOC-001）。compact 恢复仍属 Skill 指导，不在今日实现。
```
