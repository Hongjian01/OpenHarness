# Day 17：G5 人工总验收（停止功能开发）

## 今日目标

**停止增加 G5 功能。** 对 Day 16 已回填 PASS 的 META-001 / CDS-005 / VAL-001 / SKILL-002 / EVAL-004 / TEST-007 做本机人工总验收，核对 Definition of Done 第 8 条，再决定是否宣称 **Phase G5 阶段验收 PASS**。

- **SPEC 需求**：PHASE-001（G5 阶段总验收）、G5 额外 DoD、DEC-G5-001 一致性、历史 G4 baseline 完整性
- **预计投入**：3～5 小时（离线复跑 + 只读审查；真实 CDS / `real_agent` 仅在用户显式允许时）
- **完成标志**：离线门闩有当日命令结果；G5 边界未被突破；`climate-real-9b592ba.json` 未被改写；SPEC PHASE-001 要么回填「G5 人工验收 PASS」，要么诚实保留「阶段总验收未宣称」
- **上一天**：[Day 16](DAY_16_G5_PAPER_ALIGNED_MINIMAL.md)

## 今日原则

- 不新增工具、action、依赖、Selenium、Bench-85、联网 LLM judge、ECMWF Agent。
- 不以 mock/synthetic 冒充真实 CDS 或多候选真实下载。
- 不读取、不打印、不提交 `.cdsapirc` / API key。
- 不改写历史 `evals/baselines/climate-real-9b592ba.json`。
- 不自动提交/推送；人工确认后另发提交指令。
- Skill 已变、默认工具集仍为七个：MODEL-001 **默认不重跑**；仅当用户明确要求确认 Agent 顺序时另开 3× `real_agent`，并写新 baseline 文件名。

## Day 16 已声称、今日必须复核的事实

| 项 | Day 16 声称 | 今日如何证伪/确认 |
|---|---|---|
| Climate collect | 284 tests | `uv run pytest tests/test_climate --collect-only -q` |
| 默认 pytest | 286 passed / 1 skipped（含 Skill） | `CLIMATE_INTEGRATION=0` 再跑 |
| Ruff | PASS | `uv run ruff check src tests scripts evals` |
| 四场景 `real_offline` | `real_pass_rate=1.0` | 再跑 CLI，确认仍为 4 个核心场景 |
| EVAL-004 场景 | `report_quality_smoke` 未加入默认四场景顺序 | 核 `_REAL_OFFLINE_ORDER` 与 CLI 报告 traces 条数 |
| 第八工具 | 可选注册，默认七工具 | `test_default_registry_has_exact_climate_tools` + `test_optional_validate_tool_does_not_replace_core_seven` |
| 失败码 | `CLIMATE_METADATA_REJECTED` / `CLIMATE_VALIDATION_FAILED` | 错误表 + 对应失败测试 |
| 非目标 | 无 Selenium / 无自由 PLAN / 无代码执行 | 源码 import 扫描 + Skill 禁令测试 |
| G4 baseline | 未改写 `climate-real-9b592ba.json` | `git diff -- evals/baselines/climate-real-9b592ba.json` 必须为空 |

## 硬约束（与 DEC-G5-001 一致）

- 不修改 QueryEngine 执行语义。
- 不把第八工具静默并入默认 registry。
- 不上 Bench-85；不把 `report_quality_smoke` 写成论文 Report Score。
- 真实网络仅用户书面允许后运行 `climate_integration`；多候选真实 CDS **不是** 本验收 MUST。

## 完整操作流程

### 1. 工作区分类（20 分钟）

```powershell
git status --short --branch
git diff --stat
git diff --check
```

分类：

- Day 16 G5 源码/测试/Skill/Eval/SPEC。
- 会话前已有、非 G5 的改动（例如 `permission_mode` / Trace `run_id`）。
- 不应提交：凭证、真实 NetCDF、`.part`、`evals/reports/`、简历草稿。

`git diff -- src/openharness/engine/query.py src/openharness/engine/query_engine.py` 必须为空。

### 2. 需求追踪抽查（40 分钟）

只抽 G5 MUST 与 PHASE-001，对照 SPEC 第 16 节 **当场 collect 的 node ID**，不要抄 Day 16 日终报告：

```text
META-001 / CDS-005 / VAL-001 / SKILL-002 / EVAL-004 / TEST-007 / PHASE-001
→ 实现文件
→ pytest node ID（collect-only）
→ 当日命令结果
→ PASS 或降回 GAP
```

无当日命令结果不得把 PHASE-001 写成「G5 阶段验收 PASS」。

### 3. 离线验收矩阵（1.5～2 小时）

必跑：

```powershell
uv run pytest tests/test_climate --collect-only -q
uv run pytest tests/test_climate tests/test_skills/test_climate_skill.py -q
uv run ruff check src tests scripts evals
uv run python -m evals --suite climate --mode real_offline
uv run python -m evals --suite climate --mode synthetic_dry_run
uv run python -m evals --suite climate --mode real_offline --scenario report_quality_smoke
git diff --check
git diff -- evals/baselines/climate-real-9b592ba.json
```

记录：collected / passed / skipped / failed、四场景是否仍为 4 条、`report_quality_smoke` 单独通过、Ruff、baseline diff 为空。

全量 `uv run pytest -q` **建议跑**；Windows 上游失败不计入 Climate / G5。若时间不够，在日终标明「全量未跑」而非假装通过。

### 4. G5 边界只读审查（45 分钟）

按 blocker / high / medium / low 输出，至少覆盖：

- `metadata.py` / `validate.py` 未 import selenium、playwright、cdsapi、subprocess。
- `climate_validate_artifacts` 输入 `extra=forbid`，无 `code` / `shell` / `expr`。
- 多候选未把失败伪装成 sample；审计字段无密钥与绝对路径。
- Skill 仍禁止第五类 action 与任意 Python。
- Eval 场景 description 含「不是 Bench-85 / 不是 Report Score 替代」。
- 默认 registry 恰好七个 `climate_*` 工具。

只修 **blocker / high**。禁止借验收加功能。

### 5. MODEL-001 决策（默认跳过）

| 选择 | 条件 | 动作 |
|---|---|---|
| **A. 不重跑（默认）** | 默认仍七工具；只 Skill 文本变化；不对外宣称「Skill 变更后 Agent 3/3 仍成立」 | 日终写明：历史 baseline 仍有效于其当时 fingerprint；Skill 变更后 Agent 顺序未重新取证 |
| **B. 另开 3× `real_agent`** | 用户明确允许网络与模型费用 | 新文件 `evals/baselines/climate-real-<commit>.json`；禁止覆盖 `9b592ba` |

本验收清单 **不把 B 列为 MUST**。

### 6. 回填 SPEC 与日终（30 分钟）

仅当第 3 步离线矩阵全部通过、第 4 步无未修 blocker：

- PHASE-001：补「Day 17 G5 本机人工总验收 PASS」；状态改为可宣称 G5 阶段验收，或保持「需求 PASS + 阶段验收 PASS」。
- 页首版本行去掉「阶段人工总验收未宣称」（若确实通过）。
- 无证据则保持 Day 16 表述，不升级 PHASE-001。

## 今日主 Prompt

```text
执行 ClimWorkflow Day 17：G5 人工总验收。

今天禁止新增功能。先阅读 SPEC 第 14A、15、16、17、18 节与
docs/climate-agent/daily/DAY_17_G5_HUMAN_ACCEPTANCE.md、
docs/climate-agent/daily/DAY_16_G5_PAPER_ALIGNED_MINIMAL.md。

硬约束：
- 不修改 QueryEngine；不把第八工具并入默认 registry；
- 不引入 Selenium / 自由 action / 代码执行 / Bench-85；
- 不改写 climate-real-9b592ba.json；不读取/打印/提交凭证；
- 不重跑 real_agent，除非用户本回合明确要求。

顺序：
1. 分类 git status/diff；确认 engine 无 Climate 改动、baseline 无 diff；
2. collect G5 node ID 并对照 SPEC 第 16 节；
3. 跑离线验收矩阵并记录真实数字；
4. blocker/high/medium/low 只读审查，只修 blocker/high；
5. 按证据回填 PHASE-001 或诚实保留未宣称；
6. 输出日终报告；不提交、不推送，除非用户明确要求。
```

## 分步骤 Prompt

```text
只做工作区分类与敏感产物扫描；列出拟提交/禁止提交文件，不跑测试、不改代码。
```

```text
只 collect 并核对 G5 需求 node ID 与 SPEC 第 16 节是否一致；不一致标 GAP。
```

```text
只跑 Day 17 离线验收矩阵并记录结果，不修复、不回填 SPEC。
```

```text
对 G5 变更做 blocker/high/medium/low 审查；重点：凭证、Selenium、默认七工具、CDS-004、Eval 真实性。
```

```text
根据当日命令结果回填 PHASE-001；无完整离线矩阵不得标 G5 阶段验收 PASS。
```

## 验收清单

- [x] 当日 `git status` 已分类；无凭证/真实数据/`.part`/`evals/reports` 进入拟提交集。
- [x] `query.py` / `query_engine.py` 无 Climate diff。
- [x] `evals/baselines/climate-real-9b592ba.json` 无 diff。
- [x] Climate collect 与 SPEC TEST-007 当日数字一致（或文档已改正）。
- [x] `CLIMATE_INTEGRATION=0` 下 Climate + Skill pytest 全绿（1 skipped = integration）。
- [x] Ruff PASS；`git diff --check` 干净。
- [x] 四场景 `real_offline` `real_pass_rate=1.0`（恰好 4 条核心 traces）。
- [x] `--scenario report_quality_smoke` 通过，且未冒充 Bench-85。
- [x] 默认 registry 仍七工具；validate 仅可选注册。
- [x] 无 Selenium / 自由 PLAN / 代码执行回归。
- [x] PHASE-001 已按证据升级或诚实未宣称。
- [x] 未提交、未推送，除非用户另发指令。

## 风险与止损

- 离线矩阵失败：先定级再修；禁止为了绿灯删测试或放宽硬断言。
- 发现默认 registry 已变成八工具：停止验收，开 SPEC 变更，不在 Day 17 内「顺便合入」。
- 范围滑向 Bench-85 / Selenium / 自由 PLAN：停止并退回 DEC-G5-001。
- 时间不够：优先离线矩阵 + baseline 完整性 + PHASE-001 诚实表述；全量 pytest 与 `real_agent` 可标未跑。

## 日终报告模板

```text
Day 17：
- 分支 / HEAD / dirty：
- Climate collect：
- Climate+Skill pytest（CLIMATE_INTEGRATION=0）：
- Ruff / git diff --check：
- real_offline 四场景：
- report_quality_smoke：
- baseline 9b592ba diff：
- QueryEngine diff：
- 默认工具数量：
- blocker/high：
- PHASE-001：
- MODEL-001：未重跑 / 已另写新 baseline
- 剩余 GAP：
- 是否建议提交：
```

## 日终报告（2026-09-03）

```text
Day 17：
- 分支 / HEAD / dirty：feat/climworkflow-mvp @ 327cd49；working tree dirty（G5 + 会话前 permission_mode/run_id；未提交）
- Climate collect：284 tests（test_metadata.py 6、test_validate.py 5、test_cds.py 29、test_evals.py 33）；与 SPEC TEST-007 一致
- Climate+Skill pytest（CLIMATE_INTEGRATION=0）：286 passed, 1 skipped（skip = climate_integration）
- Ruff / git diff --check：PASS / 干净
- real_offline 四场景：real_pass_rate=1.0；traces=4（sample_pipeline / cached_inspect / multiturn_recovery / pre_tool_output_guard）；report_quality_smoke 不在 _REAL_OFFLINE_ORDER
- report_quality_smoke：单独 CLI 通过；1 trace；report_is_bench85=false；report_rule_score=9；YAML 声明不是 Bench-85 / 不是 Report Score 替代
- baseline 9b592ba diff：空
- QueryEngine diff：空（query.py / query_engine.py）
- 默认工具数量：7；climate_validate_artifacts 仅 include_validate=True
- blocker/high：无（未改源码）
- PHASE-001：Day 17 G5 本机人工总验收 PASS
- MODEL-001：未重跑（选择 A）；历史 9b592ba 仍有效于当时 fingerprint
- 全量 pytest：1415 passed, 23 failed, 12 skipped；23 fail 均为上游 Windows（autopilot/engine/hooks/ohmo/sandbox/cron/swarm/tasks/bash/ui/shell），不含 Climate / G5
- 剩余 GAP：联网 LLM judge（刻意不做）；Bench-85（非目标）；真实 CDS 多候选冒烟（需用户许可）；Skill 变更后 Agent 顺序未重新取证
- 是否建议提交：建议用户审阅后另发提交指令。拟提交 G5 源码/测试/Skill/Eval/SPEC/日计划，以及会话前 permission_mode 与 Trace.run_id 修复。禁止提交：简历草稿、evals/reports、凭证、真实 NetCDF、.part
```

## 验收后补跑（2026-09-03，用户显式允许）

顺序：**A → B（仍七工具）→ C（改默认八工具，不再跑 Agent）**。

- **路径 A**：`test_real_cds_offgrid_candidates_are_audited` PASS（约 56s）。off-grid area 展开 3 个候选（`identity` / `area_quantized` / `area_outer`）；真实 retrieve 成功、无 sample fallback。未打印凭证。
- **路径 B**：`uv run python -m evals --suite climate --mode real_agent --agent-config evals/configs/climate-real.json --runs 3 --baseline-out evals/baselines/climate-real-g5-skill.json` 退出码 0，`passes=3/3`。三次均按核心七工具 DAG 顺序。未覆盖 `climate-real-9b592ba.json`。工作区 dirty，fingerprint 含 dirty digest。
- **路径 C**：`create_climate_tool_registry(include_validate=True)` 为默认；`unknown_tools_forbidden` 允许第八工具；`climate_dag_order` 不强制调用。未再跑真实 CDS / `real_agent`。
