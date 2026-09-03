# Day 16：G5 论文对齐最小增量（元数据 / 窄多候选 / 产物校验 / Skill / 轻量报告评测）

## 今日目标

在 **不推翻 G0～G4 契约** 的前提下，按论文第三章能力缺口中「最小改动可做」的子集启动 **Phase G5**：

1. 静态 CDS 元数据目录（官方/冻结 schema，**不用 Selenium**）；
2. 窄多候选 CDS 请求变体（合法参数组合，非代码生成）；
3. 产物规则校验工具（单位/非空/变量/覆盖）；
4. Skill / 提示增强（仍限四类 `action`）；
5. 轻量报告质量评测（规则分 + 可选离线 LLM-as-judge fixture，**不是** Bench-85）。

- **SPEC 需求**：META-001、CDS-005、VAL-001、SKILL-002、EVAL-004、TEST-007、PHASE-001（G5）、DEC-G5-001
- **预计投入**：6～8 小时（以离线 RED→GREEN 为主；真实 CDS/Agent 仅在用户显式允许时冒烟）
- **完成标志**：上述 MUST 有实现与 pytest node ID；默认 CI 仍禁网；不引入任意代码执行 / 新科学 action / Selenium / ECMWF Agent / Bench-85
- **上一天**：[Day 15](DAY_15_FINAL_ACCEPTANCE_HANDOFF.md)
- **下一天**：[Day 17](DAY_17_G5_HUMAN_ACCEPTANCE.md)（G5 人工总验收；停止功能开发）

## 与论文对齐的边界（必读）

| 论文缺口 | Day 16 是否做 | 说明 |
|---|---|---|
| 真正的 PLAN-AGENT（IVT/SPI/TC 自由拆步） | **否** | 动作面仍为 `acquire_data \| inspect_dataset \| analyze_plot \| write_report` |
| CODING-AGENT / 安全沙箱执行代码 | **否** | SPEC 非目标保持：禁止执行用户/生成 Python |
| ECMWF Agent + Selenium 元数据抓取 | **否** | 只做 **静态/官方冻结 schema**；不引入浏览器自动化；不新增 S2S Agent |
| 多候选科学纠错 + 语义验证 | **窄做** | 多候选仅限 CDS 合法请求变体；语义验证先做 **规则校验**，可选轻量报告评分 |
| Bench-85 + Report Score 全套 | **否** | 只做轻量报告评测入口与离线 fixture |

自然语言入口不变：用户可用自然语言；落盘计划必须是结构化 DAG。外层 LLM 可在四类动作内填参，Climate 包不做自由分解器。

## 预期文件

```text
docs/climate-agent/SPEC.md                          （G5 契约已先评审写入）
docs/climate-agent/daily/DAY_16_G5_PAPER_ALIGNED_MINIMAL.md
src/openharness/climate/metadata.py                 （NEW：静态 CDS schema 目录）
src/openharness/climate/cds.py                      （EXTEND：schema 校验 + 窄候选）
src/openharness/climate/validate.py                 （NEW：产物规则校验）
src/openharness/climate/pipeline.py                 （EXTEND：validate 编排）
src/openharness/climate/tools.py                    （EXTEND：climate_validate_artifacts）
src/openharness/climate/registry.py                 （EXTEND：第 8 工具可选注册）
src/openharness/climate/models.py                   （EXTEND：校验结果 artifact / 错误码）
src/openharness/climate/errors.py                   （EXTEND：CLIMATE_VALIDATION_FAILED 等）
.openharness/skills/climate-ds/SKILL.md             （EXTEND：四类动作内规划指导）
evals/climate/assertions.py                        （EXTEND：报告规则断言）
evals/climate/scenarios/report_quality_smoke.yaml   （NEW：离线轻量报告场景）
tests/test_climate/test_metadata.py                 （NEW）
tests/test_climate/test_validate.py                 （NEW）
tests/test_climate/test_cds.py                      （EXTEND：候选变体）
tests/test_climate/test_tools.py / test_evals.py    （EXTEND）
tests/test_skills/test_climate_skill.py             （EXTEND：SKILL-002）
```

先写失败测试与契约，再实现。不得先改 QueryEngine 语义。

## 安全检查

运行前：

```powershell
git status --short --branch
uv run pytest tests/test_climate -q
uv run ruff check src tests scripts evals
```

确认：

- 不读取、不打印、不提交 `.cdsapirc` / API key。
- 新模块不得 import Selenium / playwright / 浏览器驱动。
- 新工具不得接受或执行 `code` / `shell` / `expr` 字段。
- 默认 `CLIMATE_INTEGRATION=0`；真实网络仅用户显式允许时运行。
- 不把 mock/synthetic 标成真实 baseline；不改写历史 `climate-real-9b592ba.json` 证据。

## 完整操作流程

### 1. 冻结 DEC-G5-001 并对照 SPEC（30 分钟）

确认 SPEC 第 14A / 15 / 16 / 18 节已写入 G5 需求且状态为 GAP。开放决策必须在编码前关闭或标为不阻塞。

冻结摘要：

- 元数据：**静态 JSON/模块常量**，来源标注 URL 与检索日；禁止 Selenium。
- 多候选：同一 `CdsRequestInput` 科学意图下，最多 **3** 个已登记合法变体；顺序尝试；首次成功即停；计入审计字段，不静默改 `requested_mode`。
- 校验：新工具 `climate_validate_artifacts`（或等价只读后置步骤）；规则优先；失败码 `CLIMATE_VALIDATION_FAILED`。
- Skill：强化「自然语言 → 四类动作参数」示例；禁止暗示可发明第五类 action。
- 评测：离线规则断言必跑；可选 LLM judge 仅 `synthetic_dry_run` 或显式 fixture，不得默认联网。

### 2. META-001：静态 CDS schema 目录（1～1.5 小时）

实现 `metadata.py`（名称以 SPEC 为准）：

- 对冻结 dataset（至少 `reanalysis-era5-single-levels`）提供：variables、format、area 边界、日期跨度、可选「合法变体」列表。
- `validate_cds_request_against_catalog(request) -> None | ClimateError`。
- 与现有 `formats.DATASET_VARIABLES` / allowlist **单一事实来源**或明确同步测试，禁止两套互相矛盾。

测试：

- 合法请求通过；
- 未知变量 / 超界 area / 超长日期失败且脱敏；
- 模块不 import cdsapi / selenium。

### 3. CDS-005：窄多候选（1～1.5 小时）

在 acquire(cds) 路径：

- 从 catalog 展开 ≤3 个候选 payload（例如 format 偏好、同等合法 area 量化、日期拆分策略中已登记者）；
- 每个候选走现有 `.part` + magic 校验；
- timeout/rate-limit 仍遵守 CDS-003（每候选内最多 3 次 backoff）；
- Context/ToolResult 记录：`candidate_index`、`candidate_count`、`winning_candidate`（无密钥）；
- **不得**因此把失败伪装成 sample（仍受 CDS-004 约束）。

先 mock 测试：候选 1 永久失败 → 候选 2 成功；三候选皆败返回原错误类。

### 4. VAL-001：产物规则校验（1.5～2 小时）

新增只读校验（优先独立工具，避免破坏七工具既有 DAG 硬断言时可用「可选第八工具」+ Skill「report 前建议调用」）：

规则至少覆盖：

- dataset artifact 非空且 magic/扩展名一致；
- inspect profile 存在且含约定字段（variables / dims / 有界统计）；
- plot/report 存在；report 为 UTF-8 Markdown，含 title 与相对路径引用，无绝对路径/密钥；
- 科学 CSV/NetCDF：声明变量存在；数值列非全 NaN（有界采样）。

失败：`ok=false`，`CLIMATE_VALIDATION_FAILED`，`retryable=false`（除非 SPEC 另定）。

不得修改源数据文件。

### 5. SKILL-002：四类动作内规划指导（30～45 分钟）

更新 `.openharness/skills/climate-ds/SKILL.md`：

- 自然语言目标如何映射到 `objective` + 标准四步 DAG；
- sample / local / cds 选择规则；
- NetCDF 用 histogram + `y=t2m` 等已冻结约定；
- 遇错先 `climate_read_context`；
- **明确禁止**：声称可增加 SPI/IVT/TC 等新 action；禁止建议执行任意 Python。

测试：frontmatter + 关键禁令字符串断言。

### 6. EVAL-004：轻量报告质量（1 小时）

- 新增离线 scenario（可用既有 sample 产物或 fixture report）；
- 硬断言：报告章节/相对路径/脱敏/最小字数或必含字段；
- 可选：本地规则打分 0～10 写入 Trace（非 GPT-4o 联网）；若引入 LLM judge，必须默认关闭且无密钥入库。

不得宣称替代 Climate-Agent-Bench-85。

### 7. 回归与门闩（45 分钟）

```powershell
uv run pytest tests/test_climate -q
uv run pytest tests/test_skills/test_climate_skill.py -q
uv run ruff check src tests scripts evals
uv run python -m evals --suite climate --mode real_offline
uv run python -m evals --suite climate --mode synthetic_dry_run
git diff --check
git status --short
```

仅当用户显式允许网络时：

```powershell
uv run pytest -m climate_integration tests/test_climate/test_cds.py -q
```

G5 **不要求**重跑 3× `real_agent` baseline；若改动 Skill/工具名影响 Agent 顺序，须在日终报告标明「baseline 可能失效，需另开日重跑 MODEL-001」。

### 8. 回填 SPEC 矩阵

将 META-001 / CDS-005 / VAL-001 / SKILL-002 / EVAL-004 / TEST-007 从 GAP 更新为 PASS，并填写真实 node ID。无证据不得标 PASS。

## 今日主 Prompt

```text
执行 ClimWorkflow Day 16：G5 论文对齐最小增量。

先阅读 docs/climate-agent/SPEC.md 第 3、10、14A、15、16、18 节与
docs/climate-agent/daily/DAY_16_G5_PAPER_ALIGNED_MINIMAL.md。

硬约束：
- 不修改 QueryEngine 执行语义；
- 不新增自由科学 action；不执行任意 Python/Shell；
- 不引入 Selenium/浏览器自动化；不实现 ECMWF S2S Agent；
- 不上 Bench-85；不把 mock 当真实 baseline；
- 不读取/打印/提交凭证。

顺序：
1. 确认 DEC-G5-001 与需求 ID 已在 SPEC；
2. RED：metadata / validate / cds 候选 / Skill / eval 失败测试；
3. GREEN：最小实现并通过 Climate pytest + Ruff + real_offline；
4. 回填 SPEC 矩阵 node ID；
5. 输出日终报告；不提交、不推送，除非用户明确要求。
```

## 分步骤 Prompt

```text
只审查 SPEC 第 14A 节与 DAY_16：列出今日 MUST、非目标与文件清单，不写业务代码。
```

```text
只实现 META-001 静态 schema 与失败测试；禁止 Selenium 与网络。
```

```text
只实现 CDS-005 窄多候选（mock）；验证审计字段与 CDS-004 不冲突。
```

```text
只实现 VAL-001 产物规则校验与工具契约；不执行用户代码。
```

```text
只更新 climate-ds Skill（SKILL-002）与测试；禁止暗示自由 PLAN/代码执行。
```

```text
只加 EVAL-004 离线报告规则断言与 scenario；默认不联网。
```

```text
回填 SPEC 矩阵；无 pytest node ID 的需求保持 GAP。
```

## 验收清单

- [x] DEC-G5-001 已冻结且与实现一致。
- [x] META-001：静态目录校验 PASS；无 Selenium。
- [x] CDS-005：≤3 候选 mock 路径 PASS；审计字段脱敏。
- [x] VAL-001：规则校验 PASS；不改源数据。
- [x] SKILL-002：指导增强且禁止自由 action/代码执行有测试。
- [x] EVAL-004：离线轻量报告断言 PASS。
- [x] 默认 CI/pytest 仍禁网；历史 G4 baseline 未被篡改冒充。
- [x] SPEC 矩阵已回填或诚实保留 GAP。
- [x] 未提交凭证、真实 NetCDF、`.part`、临时 workspace。

## 风险与止损

- 若「第八工具」破坏既有「恰好七工具」断言：优先采用 **可选注册** 或 **pipeline 内嵌校验钩子**（report 成功前自动规则检查），并更新 REG-001/TOOL-BASE 相关测试口径；不得静默删减旧断言。
- 多候选若导致配额暴涨：严格 ≤3，且仅 mock 默认覆盖；真实 CDS 需用户许可。
- 一旦范围滑向自由 PLAN / 代码沙箱 / Selenium：停止并开 SPEC 变更评审，不在 Day 16 内实现。
- 时间不够：优先 META-001 + VAL-001 + SKILL-002；CDS-005 / EVAL-004 可标部分 PASS 并在日终列出剩余 GAP。

## 日终报告模板

```text
Day 16：
- DEC-G5-001：
- META-001：
- CDS-005：
- VAL-001：
- SKILL-002：
- EVAL-004：
- Climate pytest：
- real_offline：
- Ruff：
- SPEC 矩阵回填：
- 对 G4 baseline 影响：
- 剩余 GAP：
- 是否建议提交：
```

## 日终报告（待填写）

```text
Day 16：
- DEC-G5-001：已冻结并按冻结值实现。元数据静态目录；≤3 CDS 合法候选；规则校验可选第八工具；Skill 四类动作指导；离线报告规则断言。失败码冻结 CLIMATE_METADATA_REJECTED。默认 registry 仍七工具。禁止 Selenium / 自由 PLAN / 代码执行 / Bench-85 / ECMWF Agent。
- META-001：PASS。tests/test_climate/test_metadata.py::test_legal_request_passes_catalog；::test_unknown_variable_is_metadata_rejected_and_redacted；::test_out_of_bounds_area_is_metadata_rejected；::test_excessive_date_span_is_metadata_rejected；::test_catalog_is_single_source_with_formats_allowlist；::test_metadata_module_does_not_import_selenium_or_cdsapi
- CDS-005：PASS。::test_expand_cds_candidates_max_three_and_keeps_format；::test_candidate_first_permanent_fail_second_succeeds；::test_all_candidates_fail_returns_original_error_class；::test_candidate_audit_is_in_toolresult_and_does_not_imply_fallback
- VAL-001：PASS。tests/test_climate/test_validate.py 五项 + tests/test_climate/test_registry.py::test_optional_validate_tool_does_not_replace_core_seven。climate_validate_artifacts 只读、extra=forbid，默认不注册。
- SKILL-002：PASS。tests/test_skills/test_climate_skill.py::test_climate_skill_natural_language_to_four_actions_and_forbids_free_plan
- EVAL-004：PASS。evals/climate/scenarios/report_quality_smoke.yaml；::test_report_quality_smoke_yaml_disclaims_bench85；::test_report_quality_rules_assertion_on_fixture_trace；::test_report_quality_smoke_real_offline。未加入默认四场景顺序。
- Climate pytest：collect 284；CLIMATE_INTEGRATION=0 下 tests/test_climate + test_climate_skill 286 passed, 1 skipped
- real_offline：四核心场景 real_pass_rate=1.0；synthetic_dry_run 已跑并标记 synthetic
- Ruff：uv run ruff check src tests scripts evals PASS
- SPEC 矩阵回填：META-001 / CDS-005 / VAL-001 / SKILL-002 / EVAL-004 / TEST-007 均为 PASS 并填 node ID。PHASE-001：G5 需求 PASS，阶段总验收未宣称。
- 对 G4 baseline 影响：默认工具集仍七个，未改 climate-real-9b592ba.json。Skill 正文增强，real_agent fingerprint 可能变化；未重跑 MODEL-001，建议另开日评估。
- 剩余 GAP：G5 阶段人工总验收；联网 LLM judge（刻意不做）；Bench-85（非目标）；真实 CDS 多候选冒烟（需用户许可）
- 是否建议提交：GREEN 已完成，建议用户审阅后提交；本次未提交、未推送。勿提交 .cdsapirc、真实 NetCDF、.part、evals/reports 临时产物、简历草稿。
```
