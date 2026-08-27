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

- [ ] G2 在 G3 开始前正式 PASS。
- [ ] 全量 pytest 与 Ruff 通过。
- [ ] 7 工具、sample/local E2E、非法顺序/路径均有证据。
- [ ] Eval schema 和 TraceRecord 严格校验。
- [ ] hard assertion 失败产生非零退出码。
- [ ] synthetic 不能计入真实成功率。
- [ ] G3 的 real_agent 明确不可执行且不计入通过率。
- [ ] 未实现 Day 08/09 内容。

## 风险与止损

- 全量测试时间过长不代表可跳过；可先并行定位，但 Gate 最终必须完整运行。
- 不要把“能加载 scenario”写成“scenario 真实通过”。
- 当前 Hatch wheel 不包含根目录 `evals`；G3 只承诺仓库根目录执行 `uv run python -m evals`，
  安装后入口另行评审，不在今天扩大打包范围。
- G2 blocker 占满全天时，Day 08 顺延；阶段门优先于 15 天日历。

## 日终报告模板

```text
Day 07：
- G2 Gate：PASS/GAP
- G2 blocker/high 修复：
- 全量 pytest/Ruff：
- SPEC 回填：
- Eval schema/runner：
- synthetic 输出标记：
- hard assertion 退出码：
- Day 08 是否可开始：
```
