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

- [ ] 三个场景均为 real_offline 真实执行。
- [ ] 每个场景有硬断言，不只看进程退出码。
- [ ] multiturn 不共享旧内存状态。
- [ ] Trace 字段完整且无绝对路径/凭证。
- [ ] synthetic 与真实统计分离。
- [ ] Eval 运行产物未污染 Git。

## 风险与止损

- 禁网可通过 monkeypatch/socket guard 证明；不要仅声称没有网络调用。
- Eval runner 不应复制业务逻辑，应调用公开工具边界。
- 如果场景暴露 G2 bug，先记录需求归属并最小修复，重跑 G2 Gate 相关测试。

## 日终报告模板

```text
Day 08：
- sample_pipeline：
- cached_inspect：
- multiturn_recovery：
- real_offline 命令结果：
- Trace/脱敏检查：
- PASS/GAP 需求：
- 回归/Ruff：
- Day 09 blocker：
```
