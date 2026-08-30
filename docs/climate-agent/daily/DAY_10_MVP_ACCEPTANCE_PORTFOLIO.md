# Day 10：离线工程 MVP 总验收与求职证据

## 今日目标

停止增加功能，完成 G3 总验收、只修 blocker/high，并形成可复核的简历项目证据包。

- **SPEC 需求**：G0～G3 全部适用需求、PHASE-001、DOC-001、CI-001
- **预计投入**：6～8 小时
- **完成称谓**：仅在全部通过后称为 **ClimWorkflow Offline Engineering MVP**
- **上一天**：[Day 09](DAY_09_G3_HOOK_SKILL_README.md)
- **下一天**：[Day 11](DAY_11_G4_TECHNICAL_SPIKE.md)

## 今日禁止事项

- 不增加新工具、新数据格式、新 UI、CDS 或真实模型。
- 不为了获得好看数字删除失败测试或降低硬断言。
- 不虚构测试数量、成功率、性能或“生产级”结论。
- 不自动提交/推送；人工验收后另行请求。

## 完整操作流程

### 1. 工作区与范围审计（45 分钟）

```powershell
git status --short --branch
git diff --check
```

让 Cursor 对照 SPEC 列出：

- G0～G3 每个需求 ID。
- 实现文件。
- 实际测试 node ID。
- 当前 PASS/GAP。
- 阶段外文件、缓存、凭证、运行产物。

搜索并确认无 `.env`、`.cdsapirc`、token、API key、绝对本机路径进入变更。

### 2. 四层验证（2～3 小时）

第一层，Climate：

```powershell
uv run pytest tests/test_climate -q
```

第二层，OpenHarness 全量：

```powershell
uv run pytest -q
```

第三层，质量：

```powershell
uv run ruff check src tests scripts evals
git diff --check
```

第四层，真实离线 Eval：

```powershell
uv run python -m evals --suite climate --mode real_offline
uv run python -m evals --suite climate --mode synthetic_dry_run
```

记录真实：

- 测试 collected/passed/skipped/failed。
- 4 个场景结果及耗时。
- 7 工具序列。
- artifact 数量和摘要验证。
- 多轮恢复最终状态。
- Hook blocked provenance。

### 3. 只读验收与定级（45 分钟）

Prompt 要求输出 blocker/high/medium/low。判断规则：

- blocker：安全逃逸、Context 损坏、恢复错误、硬断言虚假、全链路不可运行。
- high：主要工具契约错误、幂等/锁/原子写缺陷、文档不可复现。
- medium/low：不影响 MVP 契约的可维护性或表达问题。

### 4. 只修 blocker/high（1～2 小时）

每个修复：

1. 先添加/确认复现测试。
2. 最小修复。
3. 运行受影响测试。
4. 重新运行四层验证。

不顺手重构。

### 5. SPEC 与文档收口（45 分钟）

- 第 16 节回填实际 node ID 与 PASS。
- G3 DoD 全部满足后更新称谓。
- README 中测试数字使用本次真实结果。
- 明确 G4 未完成，不写“支持真实 ERA5/CDS”。

### 6. 求职证据包（1 小时）

建议在 README/docs 中保留：

- 一张清晰架构图：Agent loop → 7 Tools → Repository/State → `.climate/` → Eval。
- 一段 3～5 分钟 Demo 脚本。
- 一份真实 Eval 输出样例（脱敏、不含临时绝对路径）。
- 关键工程取舍：Memory ≠ Context、PRE Hook guard、WAL、SVG fallback、synthetic ≠ real。
- 真实指标清单。

简历表述模板（数字必须替换为实测）：

```text
基于 OpenHarness 从零设计并实现可恢复的气候数据 AI Agent，构建 7 个类型化工具与版本化工作流
状态机，通过原子写、双层文件锁、乐观并发控制和 WAL 恢复保障任务一致性；建立覆盖路径攻击、
多轮恢复与 Hook 拦截的离线 Eval，完成 X 个测试、4 个硬断言场景，真实离线场景通过率 X%。
```

面试讲解顺序：

```text
为什么不能只靠聊天上下文
→ Context/状态机设计
→ 文件安全和并发一致性
→ 7 工具如何受依赖与幂等约束
→ Eval 如何证明真实执行
→ 失败案例与工程取舍
```

## 今日主 Prompt

```text
执行 ClimWorkflow Day 10：G0～G3 Offline Engineering MVP 总验收。

今天不增加任何功能。
先对照 SPEC 第 16～18 节，建立“需求 ID→实现→实际测试 node ID→结果”清单。
依次运行：
- uv run pytest tests/test_climate -q
- uv run pytest -q
- uv run ruff check src tests scripts evals
- uv run python -m evals --suite climate --mode real_offline
- uv run python -m evals --suite climate --mode synthetic_dry_run

然后做只读审查，按 blocker/high/medium/low 输出。
只修 blocker/high；每个修复先有复现测试，修复后重跑四层验证。
仅当全部适用需求 PASS 后更新 SPEC 和 MVP 称谓。

输出真实测试/场景/耗时指标和简历证据，不虚构数字。
不接入 G4，不访问旧目录，不提交、不推送。
```

## 分步骤 Prompt

```text
只读建立 G0～G3 需求追踪清单。任何没有真实 node ID 的 PASS 都降为 GAP，不修复。
```

```text
执行四层验收并保存摘要。失败时先定位到需求 ID，不立即扩大修复范围。
```

```text
根据验收报告只修 blocker/high。禁止新增功能或清理无关技术债。
```

```text
基于真实测试与 Eval 输出，起草两条中文简历 bullet 和 5 分钟面试讲解提纲；所有数字必须注明来源。
```

## MVP 验收清单

- [x] G0～G3 所有适用需求 PASS（均有真实 pytest node ID；G4 保持 GAP）。
- [x] Climate pytest 通过（198 passed in 52.29s）。全量 `pytest -q`：1325 passed / 23 failed / 11 skipped；失败均为 OpenHarness Windows POSIX/时区/符号链接/cmd，**0 个 Climate**（与 Day 07/09 口径一致，不作为 Climate Gate 否决）。
- [x] Ruff、diff check 通过。
- [x] 三个核心真实离线场景和 Hook guard 通过（4/4，`real_pass_rate=1.0`）。
- [x] sample/local Demo 可从空 workspace 复现（`test_readme_offline_demo_from_empty_workspace`）。
- [x] 多轮恢复只依赖 Context（`multiturn_recovery`：`recovery_source=disk_context`，`session1_destroyed=true`）。
- [x] 无凭证、缓存、绝对路径进入 Trace；Eval JSON 报告 gitignore 且验收后删除。
- [x] README 不夸大 G4 能力。
- [x] 简历指标全部可由命令输出复核。

## 是否允许提交

只有人工确认上述清单后，另开请求：

```text
请提交 G1～G3 已验收的 Offline Engineering MVP 修改。先检查完整 status/diff/最近提交风格；
只暂存相关文件，不提交凭证、缓存或 Eval 运行产物；提交后验证 status，不推送。
```

## 日终报告模板

```text
Day 10 / MVP Gate：
- Climate pytest：
- 全量 pytest：
- Ruff：
- real_offline 场景与耗时：
- synthetic 标记：
- blocker/high 及修复：
- G0～G3 PASS/GAP：
- MVP 称谓是否成立：
- 实测简历指标：
- G4 开始条件：
```

## Day 10 总验收记录（2026-08-28）

工作区：分支 `feat/climworkflow-mvp`，HEAD `3e9e236 feat(climate): add G1 core state foundation`。
`git diff --check` 清洁。未发现 `.env` / `.cdsapirc` / token 进入变更。`engine/query.py` 与 `query_engine.py` 无 Climate 字符串。未访问旧目录，未提交、未推送。

### 四层验证

| 层 | 命令 | 结果 |
|---|---|---|
| 1 | `uv run pytest tests/test_climate -q --durations=20` | 198 passed in 52.29s |
| 2 | `uv run pytest -q --durations=20` | 1325 passed, 23 failed, 11 skipped in 137.30s |
| 3 | `uv run ruff check src tests scripts evals`；`git diff --check` | All checks passed；diff check 退出 0 |
| 4a | `uv run python -m evals --suite climate --mode real_offline` | exit 0，`real_pass_rate=1.0`，墙钟 10850 ms |
| 4b | `uv run python -m evals --suite climate --mode synthetic_dry_run` | exit 0，stdout 含 `SYNTHETIC DRY-RUN`，墙钟 2644 ms |

Collect：`tests/test_climate` + `test_climate_skill.py` = 200（198 Climate + 2 Skill）。

全量 23 个失败均为上游 OpenHarness（autopilot/query_engine/hooks/ohmo/sandbox/cron/swarm/tasks/bash/ui/shell），无 `tests/test_climate`、无 `test_climate_skill.py`。

### real_offline 场景（本次 CLI 报告）

| 场景 | duration_ms | status | version | 工具序列 | artifact |
|---|---:|---|---:|---|---|
| `sample_pipeline` | 1211 | completed | 11 | init→plan→acquire→inspect→plot→report→read | dataset/profile/plot/report |
| `cached_inspect` | 371 | running | 6 | init→plan→acquire→inspect→inspect | dataset/profile；源未改 |
| `multiturn_recovery` | 651 | completed | 11 | …inspect→read→plot→report | dataset/profile/plot/report；`recovery_source=disk_context` |
| `pre_tool_output_guard` | 5362 | running | 8 | …plot→write_report(error) | dataset/profile/plot；无 report |

Hook：`pre_tool_use` / `climate_write_report` / `blocked=true` / `reason_code=CLIMATE_HOOK_BLOCKED`；`write_report_executed=false`；`context_version_unchanged` / `events_unchanged` / `file_tree_unchanged` 均为 true。

sample 工具耗时 ms：init 46，plan 92，acquire 113，inspect 87，plot 703，report 127，read 31。
sample CSV sha256：`sha256:e85354e49b204f4c45d056a17eb24b9415fdbea2e3ca2a4a762fcf1558e06f22`（三场景相同）。
Trace JSON 扫描无 `C:\Users` / `E:\agent` / `sk-` / `.cdsapirc`。

synthetic：`synthetic=true`，`tools_executed=false`，`model_invoked=false`，`counts_toward_real_pass_rate=false`，`real_pass_rate=null`，`duration_ms=0`，`final_run_status=not_executed`。仅 wiring 断言 `tool_sequence` PASS。

### 只读审查

**blocker**：无。

**high**：无。未改代码。

**medium**

- 本机全量 `pytest -q` 23 失败，与清单字面“全量 pytest 通过”不一致；失败为既有 OpenHarness Windows 环境问题，SPEC CI-001 已记 GAP（未推送 GitHub Ubuntu CI）。
- Eval CLI stdout 打印报告绝对路径（`wrote E:/agent/ClimWorkflow/evals/reports/...`）；Trace/ToolResult/Context 未含绝对路径。
- CI workflow 仅 `main` / `pull_request`；即使推送功能分支也不会跑 Actions。

**low**

- `evals.climate.runner.SUITE_VERSION` 仍为 `g3-foundation`。
- Trace `recovery.session1_metadata_id` 为进程内对象 id，非路径/密钥。
- matplotlib PNG sha256 跨场景不完全相同；硬断言检查 kind/存在性，CSV 摘要确定。

### 脱敏 Eval 样例（摘自本次 `climate-real_offline.json`，已删运行产物）

```json
{
  "suite": "climate",
  "mode": "real_offline",
  "synthetic": false,
  "tools_executed": true,
  "model_invoked": false,
  "counts_toward_real_pass_rate": true,
  "real_pass_rate": 1.0,
  "sample_pipeline": {
    "duration_ms": 1211,
    "final_run_status": "completed",
    "final_context_version": 11,
    "tool_sequence": [
      "climate_init_workflow",
      "climate_plan_steps",
      "climate_acquire_data",
      "climate_inspect_dataset",
      "climate_analyze_plot",
      "climate_write_report",
      "climate_read_context"
    ],
    "artifacts": [
      {"kind": "dataset", "path": ".climate/data/<run_id>/sample.csv", "size_bytes": 636},
      {"kind": "profile", "path": ".climate/output/<run_id>/profile.json", "size_bytes": 451},
      {"kind": "plot", "path": ".climate/output/<run_id>/plot-plot.png", "size_bytes": 39480},
      {"kind": "report", "path": ".climate/output/<run_id>/report.md", "size_bytes": 386}
    ]
  },
  "pre_tool_output_guard": {
    "hook_events": [
      {"sequence": 1, "event": "pre_tool_use", "tool_name": "climate_write_report", "blocked": true, "reason_code": "CLIMATE_HOOK_BLOCKED"}
    ],
    "write_report_executed": false
  }
}
```

### 5 分钟 Demo 脚本

1. `uv sync --extra dev` → `uv run pytest tests/test_climate -q`（预期 198 passed）。
2. 按 README 在空临时目录跑 `sample_pipeline`，打印 `status=completed`。
3. 销毁 Python 对象，只调用 `climate_read_context` 读盘。
4. `uv run python -m evals --suite climate --mode real_offline`（预期 4/4）。
5. 再跑 `synthetic_dry_run`，确认 SYNTHETIC 标记且不计入真实通过率。
6. 说明 G4 未做：无 CDS、无 `real_agent`。

### 简历 bullet（数字均注明命令）

1. 基于 OpenHarness 从零实现可恢复气候数据 Agent：7 个类型化工具 + 版本化状态机；原子写、双层文件锁、乐观并发与 WAL。离线 Eval 覆盖路径攻击、多轮恢复与 Hook 拦截。Climate 测试 **198 passed / 52.29s**（来源：`uv run pytest tests/test_climate -q`，2026-08-28）。
2. 真实离线 4 场景硬断言全部通过，**`real_pass_rate=1.0`**（来源：`uv run python -m evals --suite climate --mode real_offline`，墙钟 10850ms）；Hook 场景 `CLIMATE_HOOK_BLOCKED` 且 execute=0。synthetic 明确不计入通过率。未声称 CDS/ERA5。

### 面试 5 分钟提纲

1. 为什么不能只靠聊天上下文 → Memory ≠ Context，权威在 `.climate/`。
2. Context / 状态机 → schema v2、version、非法转换拒绝。
3. 文件安全与并发 → PATH 拒绝逃逸；workspace→run 锁序；`expected_version`；WAL。
4. 7 工具依赖与幂等 → 同输入 replay 不升 version；CDS 在 G2/G3 返回 `CLIMATE_FORMAT_UNSUPPORTED`。
5. Eval 如何证明真实执行 → `tools_executed=true`、禁网、硬断言失败非零退出。
6. 失败与取舍 → PRE Hook 不做 POST 回滚；SVG fallback；synthetic ≠ real；G4 未开始。

### 填写后的 Gate 摘要

```text
Day 10 / MVP Gate：
- Climate pytest：198 passed in 52.29s（collect 198）
- 全量 pytest：1325 passed, 23 failed, 11 skipped in 137.30s（0 Climate 失败）
- Ruff：PASS；git diff --check：PASS
- real_offline 场景与耗时：sample 1211ms completed；cached 371ms running；multiturn 651ms completed；hook 5362ms running blocked；墙钟 10850ms；real_pass_rate=1.0
- synthetic 标记：SYNTHETIC DRY-RUN；counts_toward_real_pass_rate=false；2644ms
- blocker/high 及修复：无；未改功能代码
- G0～G3 PASS/GAP：适用需求 PASS；G4 GAP；CI GitHub 未推送仍 GAP
- MVP 称谓是否成立：是，ClimWorkflow Offline Engineering MVP
- 实测简历指标：见上表，均可复跑命令复核
- G4 开始条件：关闭 DEC-G4-001（NetCDF/GRIB/allowlist/CI 安装）；不阻塞已验收的 G0～G3
```
