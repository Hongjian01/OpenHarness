# Day 09：G3 Hook Guard、Skill 与 README

## 今日目标

补齐可证明的 Hook 安全拦截、Agent 使用说明和从空 workspace 可复现的离线演示。

- **SPEC 需求**：HOOK-001、SKILL-001、MEM-001、DOC-001、TEST-005
- **预计投入**：6～8 小时
- **完成标志**：Hook 场景证明 execute 未发生；Skill 可加载；README Demo 可复制
- **上一天**：[Day 08](DAY_08_G3_OFFLINE_EVAL_RECOVERY.md)
- **下一天**：[Day 10](DAY_10_MVP_ACCEPTANCE_PORTFOLIO.md)

## 严格范围

允许新增/修改：

```text
evals/climate/scenarios/pre_tool_output_guard.*
tests/test_climate/test_evals.py
.openharness/skills/climate-ds/SKILL.md
tests/test_skills/test_climate_skill.py
README.md 或 docs 中由 SPEC 冻结的演示入口
```

不得新增 Climate 专用 HookEvent；使用现有 `PRE_TOOL_USE`。不得把 `POST_TOOL_USE` 当回滚机制。

## 开始前检查

```powershell
git status --short --branch
uv run pytest tests/test_climate -q
uv run python -m evals --suite climate --mode real_offline
```

让 Cursor 只读检查：

```text
src/openharness/hooks/events.py
src/openharness/hooks/executor.py
src/openharness/engine/query.py 的 PRE/POST_TOOL_USE 顺序
src/openharness/skills/ 及现有 Skill loader 测试
tests/test_hooks/test_executor.py
tests/test_skills/test_loader.py
```

## 完整开发流程

### 1. RED：PRE_TOOL_USE Guard（1～1.5 小时）

场景目标：让 Hook 在 `climate_write_report.execute` 前拒绝一个能通过工具 schema、但 summary
包含固定 `blocked-output-secret` 测试标记、违反输出策略的调用。工具自身本应接受该普通字符串，
因此可以证明阻断来源是 Hook，并证明该标记未写入 report。硬断言：

- matcher 精确命中 `climate_write_report`。
- Trace 有 PRE_TOOL_USE、blocked=true 和 reason。
- spy/monkeypatch 证明 `execute` 调用次数为 0。
- Context version、events、文件树无变化。
- 返回来源标记为 Hook，不是工具自身校验。

避免使用本来就会被 Pydantic 或路径校验拒绝的输入，否则无法证明 Hook provenance。

### 2. GREEN：Hook scenario 与 Trace 采集（1～1.5 小时）

复用现有 HookRegistry/HookExecutor。只扩展 Eval 事件采集，不修改 query loop 语义。

### 3. RED/GREEN：climate-ds Skill（1.5 小时）

使用 loader 已支持的项目目录 `.openharness/skills/climate-ds/SKILL.md`，并先确认 frontmatter
格式，再测试：

- loader 能发现并加载。
- frontmatter/名称/描述合法。
- 内容明确 7 工具顺序。
- 遇错先 read_context，不能猜成功。
- 禁止凭证进入输入/日志/Context。
- G0～G3 不调用 CDS。
- 解释 read_context 是权威恢复来源。

Skill 只提供 Agent 指导，不承载业务实现。

### 4. README 可复现演示（1.5～2 小时）

写明：

- 项目目标、当前称谓 `ClimWorkflow Offline Engineering MVP` 的适用条件。
- 安装/测试前置。
- 从空 workspace 执行 sample/local Demo。
- 预期 `.climate/` 数据、图、报告、Context。
- 模拟新会话恢复步骤。
- `real_offline` 与 `synthetic_dry_run` 的区别。
- 已知限制：无真实 CDS、非通用 DAG、workspace 外路径禁止。
- 测试命令和常见错误码。

要求另一个临时空目录按文档实际执行，不接受只读审稿。

### 5. 验证

```powershell
uv run pytest tests/test_climate/test_evals.py tests/test_skills/test_climate_skill.py -q
uv run pytest tests/test_hooks/test_executor.py tests/test_skills/test_loader.py -q
uv run python -m evals --suite climate --mode real_offline
uv run pytest tests/test_climate -q
uv run ruff check src tests scripts evals
git diff --check
git status --short
```

## 今日主 Prompt

```text
执行 ClimWorkflow Day 09 / Phase G3：Hook Guard、climate-ds Skill 与 README Demo。

阅读 SPEC 第 11～13、15～17 节和 DAY_09_G3_HOOK_SKILL_README.md，并以当前 hooks/skills loader 代码为准。

顺序：
1. 先写 pre_tool_output_guard 失败测试，证明 PRE_TOOL_USE 阻断且工具 execute=0。
2. 最小实现 Hook scenario/Trace 采集，不新增 HookEvent，不修改 QueryEngine 语义。
3. 先写 climate-ds Skill loader/内容测试，再创建 `.openharness/skills/climate-ds/SKILL.md`。
4. 编写 README 空 workspace 离线 Demo，并真实复现。
5. 跑 Hook/Skill/Eval/Climate 回归和 Ruff。

不得用工具自身拒绝冒充 Hook 拦截，不接入 CDS/真实模型，不提交、不推送。
```

## 分步骤 Prompt

```text
使用 schema 合法、summary 含固定 blocked-output-secret 标记的 write_report 输入，解释如何通过
execute spy、Context version 和文件树证明拒绝发生在 execute 之前。
```

```text
只写 Hook provenance 失败测试：事件、blocked reason、execute spy、Context version、文件树全部硬断言。
```

```text
只读确认当前 Skill frontmatter 约定后，为 `.openharness/skills/climate-ds/SKILL.md` 写加载和
关键指令测试。
```

```text
在新的临时空 workspace 严格照 README 复现，不使用开发者脑内步骤；记录所有文档缺口。
```

## 验收清单

- [ ] Hook 拦截发生在工具 execute 前。
- [ ] Context 和文件系统在 blocked 场景零变化。
- [ ] Skill 被真实 loader 加载。
- [ ] Skill 强制 Context 恢复和凭证安全。
- [ ] README 从空 workspace 可复现。
- [ ] README 不声称已有 CDS/真实模型能力。

## 风险与止损

- Command Hook 可能受 shell 平台差异影响；测试可用确定性 Hook double，但 Eval 必须走真实 HookExecutor。
- README 命令以当前仓库可执行入口为准，不发明 CLI。
- Skill 路径已由当前 loader 代码冻结；若未来 upstream 改变，先更新 SPEC，不静默换位置。

## 日终报告模板

```text
Day 09：
- Hook provenance：
- execute=0 / Context零变化证据：
- Skill loader：
- README 空 workspace 复现：
- real_offline Eval：
- PASS/GAP 需求：
- Day 10 blocker：
```
