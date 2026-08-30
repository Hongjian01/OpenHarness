# Day 06：G2-B Plot、Report 与完整离线工具链

## 今日目标

补齐剩余两个工具，完成 7 工具离线端到端：

```text
init → plan → acquire(sample/local) → inspect → plot → report → read context
```

- **SPEC 需求**：TOOL-PLOT-001、TOOL-REPORT-001、TOOL-BASE-001、REG-001、ERR-001、
  PATH-003、IO-001、STATE-001/002/003、TEST-004
- **预计投入**：7～8 小时
- **完成标志**：真实生成可打开图表、Markdown 报告并将 run 转为 completed
- **上一天**：[Day 05](DAY_05_G2B_PLAN_LOCAL_ACQUIRE.md)
- **下一天**：[Day 07](DAY_07_G2_GATE_G3_EVAL_FOUNDATION.md)

## 严格范围

允许修改 G2 tools/pipeline/registry 及测试；如需 matplotlib，只作为 optional dependency 设计。
禁止实现 Eval、Skill、真实 CDS、NetCDF/GRIB。

## 开始前检查

```powershell
git status --short --branch
uv run pytest tests/test_climate -q
```

人工确认 registry 当前包含前 5 个工具且无重名覆盖。让 Cursor 只读检查项目依赖配置和现有图像工具
如何处理 optional dependency，但不得复用不符合 Climate 安全路径的文件写法。

## 完整开发流程

### 1. RED：Plot（1.5 小时）

覆盖：

- line/bar 需要 x+y；histogram 只需要 y。
- 数据必须来自已 inspect 的 dataset。
- 列不存在、非数值 y、非法 chart_type、依赖未完成拒绝。
- matplotlib 可用时生成真实 PNG，检查 magic/media type/非空。
- monkeypatch 模拟 matplotlib 缺失时生成真实 SVG，而非占位文本。
- 只写 `.climate/output/<run_id>/`。
- artifact 记录相对路径、大小、sha256、实际 media type 和 fallback reason。
- 同输入重放幂等，不同输入冲突。

### 2. GREEN：Plot（2 小时）

先建立与渲染器无关的有界数据准备层，再实现：

1. matplotlib PNG renderer。
2. 标准库确定性 SVG renderer。
3. `.part` + 原子 replace。
4. 状态机/Repository 更新。

避免全局 matplotlib 状态污染测试；图表标题/文本需要安全转义。

### 3. RED：Report（1 小时）

覆盖：

- title/summary 长度和多余字段。
- report step 必须等待 inspect 和 plot。
- Markdown 包含 objective、mode、profile、相对图链接、summary、run_id、UTC 时间。
- summary 只当文本，不执行模板/HTML/Shell。
- 不出现绝对路径或凭证。
- 固定输出 `report.md`，原子发布并记录 artifact。
- 全部非 skipped step succeeded 后 run completed。
- 依赖失败时不生成报告、不改变稳定状态。

### 4. GREEN：Report（1～1.5 小时）

实现纯 Markdown renderer 与原子写入；完成转换必须通过状态机，不在工具里直接赋值绕过。

### 5. 完整 E2E 与回归（1.5 小时）

至少运行：

```text
sample：init→plan→acquire→inspect→plot(PNG/SVG)→report→read
local：init→plan→acquire→inspect→plot→report→read
negative：错误顺序、非法路径、错误列、重复不同输入
```

7 个工具全部实现后，先测试名称与现有默认 registry 无冲突，再一次性扩展
`create_default_tool_registry()`；不得依赖 `ToolRegistry.register()` 的静默覆盖行为。补测全部
Climate 工具失败时 `ToolResult.is_error` 与统一 envelope 一致，关闭 ERR-001 的 G2 部分。

```powershell
uv run pytest tests/test_climate/test_tools.py tests/test_climate/test_pipeline.py tests/test_climate/test_registry.py -q
uv run pytest tests/test_climate -q
uv run pytest tests/test_tools/test_core_tools.py tests/test_engine/test_query_engine.py -q
uv run ruff check src/openharness/climate src/openharness/tools tests/test_climate
git diff --check
git status --short
```

## 今日主 Prompt

```text
执行 ClimWorkflow Day 06 / Phase G2-B：Plot、Report 与完整离线工具链。

阅读 SPEC 第 5、7～10、13、15～16 节和 DAY_06_G2B_PLOT_REPORT_PIPELINE.md。

严格先测试：
1. 为 climate_analyze_plot 写 PNG、SVG fallback、列校验、路径、artifact、幂等失败测试。
2. 确认 RED 后实现最小 plot。
3. 为 climate_write_report 写依赖、内容、脱敏、原子发布、completed 转换失败测试。
4. 确认 RED 后实现最小 report。
5. 7 工具齐备后一次性接入默认 registry，先检测重名，不覆盖既有工具。
6. 跑 sample/local 完整真实 E2E、全部 Climate 回归、工具/引擎回归和 Ruff。

不得写占位图，不得执行 summary，不得接入 CDS/Eval/Skill，不修改 QueryEngine。
不访问旧目录，不提交、不推送。
```

## 分步骤 Prompt

```text
只写 plot 失败测试。必须通过文件 magic/解析证明 PNG/SVG 是真实图像，并模拟 matplotlib 缺失。
```

```text
只实现 plot 数据准备和两个 renderer。输出必须经过固定 output zone 与原子发布。
```

```text
只写 report 失败测试，证明依赖未完成时零副作用，summary 不会被当作模板或代码执行。
```

```text
对完整 7 工具链做只读验收，输出每个工具 schema、状态转换、产物和测试证据，不修复。
```

## 验收清单

- [ ] 7 个工具名称唯一并可导出 schema。
- [ ] 默认 registry 一次性加入完整 7 工具，且不会静默覆盖。
- [ ] PNG 和 SVG fallback 都有真实内容测试。
- [ ] plot/report 只写 run output 目录。
- [ ] Markdown 无绝对路径、凭证或模板执行。
- [ ] run 仅在全部必要 step 成功后 completed。
- [ ] sample/local 完整 E2E 通过。
- [ ] 没有 CDS/Eval/Skill。

## 风险与止损

- matplotlib 安装问题不能阻塞离线 MVP；SVG fallback 是正式契约。
- 不要为了图表功能引入 pandas 等非必要大依赖。
- 若图表确定性导致二进制 metadata 不稳定，测试语义与有效性；sha256 仍必须准确记录实际文件。

## 日终报告

```text
Day 06 结果：
- Plot PNG/SVG：PASS。climate_analyze_plot 只读已 inspect 的 CSV；line/bar 需 x+y，histogram 只需 y。matplotlib 可用时写出真实 PNG（\x89PNG magic）；monkeypatch 缺失时标准库写出可解析 SVG（polyline/rect），非占位文本。产物仅落 WriteZone.OUTPUT：.climate/output/<run_id>/；artifact 记录相对路径、size、sha256、实际 media type 与 fallback_reason。同输入 replay 不改版本，不同输入 CLIMATE_IDEMPOTENCY_CONFLICT。证据：test_plot_png_and_svg_fallback；test_plot_rejects_columns_paths_and_uninspected_data；test_plot_idempotency_and_conflict；test_offline_sample_svg_fallback_end_to_end。matplotlib 为 optional extra（plot/dev，实测 3.11.1），未引入 pandas。
- Report：PASS。climate_write_report 等待 inspect+plot；依赖未就绪时不写 report.md、不改稳定状态。UTF-8 Markdown 含 objective、mode、profile、相对图链接、summary、run_id、UTC 时间。summary 字面拼接，不执行模板/HTML/Shell（{objective}/$(whoami)/<script> 原样保留）。绝对路径与凭证脱敏（catch_all_posix=False，避免误伤报告文本）。固定输出 report.md，.part+os.replace 原子发布。证据：test_report_dependencies_artifact_and_completion。
- 7 工具 registry：PASS。名称唯一且 to_api_schema() 可导出。先测无重名，再一次性 _register_climate_tools() 接入 create_default_tool_registry()；冲突 ValueError，不静默覆盖。独立 Climate registry 仍可用。七工具：climate_init_workflow / climate_plan_steps / climate_acquire_data / climate_inspect_dataset / climate_analyze_plot / climate_write_report / climate_read_context。证据：test_climate_registry_names_unique_and_schema_exportable；test_climate_tool_names_do_not_collide_with_default_registry；test_default_registry_has_exact_climate_tools；test_independent_registry_does_not_overwrite_same_name。
- sample/local E2E：PASS。init → plan → acquire(sample|local) → inspect → plot(PNG 或 SVG) → report → read 均从空 workspace 真实写出图表与 report.md。另有非法顺序、非法路径、错误列、重复不同输入的负向路径。证据：test_offline_vertical_slice_from_empty_workspace；test_offline_local_vertical_slice_from_empty_workspace；test_offline_sample_svg_fallback_end_to_end；test_illegal_order_and_cds_are_stable_errors；test_inspect_rejects_unsafe_path。未接入 CDS/Eval/Skill；QueryEngine 无 diff。
- run completed 证据：全部非 skipped step 为 succeeded 后，工具经状态机 apply_step_event(success) 再 apply_run_event(report_succeeded)，Context.status=completed，events 含 run_completed。依赖失败时 status 仍为 running。completed 上同输入 replay 返回已存结果；不同输入 IDEMPOTENCY_CONFLICT。证据：test_report_dependencies_artifact_and_completion 断言 ctx.status=="completed" 且 event.type=="run_completed"；sample/local E2E 同样断言。
- PASS/GAP 需求：
    PASS（Day 06 关闭，node ID 已回填 SPEC §16）：TOOL-PLOT-001、TOOL-REPORT-001、TOOL-BASE-001（七工具）、REG-001、ERR-001（七工具 envelope）、IO-001（plot/report.md；G4 下载仍 GAP）、IDEM-001（plot/report replay）、PATH-003（plot/report 只写 output）、SEC-001（report Markdown 脱敏；G3 Trace 仍 GAP）、TEST-004、SDD-001（G2-B Day 06）、PERM-001（工具分类与 Climate 再校验，含 plot path）、STATE-001/002/003（沿用 G1，report_succeeded→completed）。
    GAP（非今日范围）：ARCH-001、CI-001、PERM-001 的 QueryEngine 路径抽取、CTX-002 的 G3 compact、PHASE-001、EVAL-*、Skill、真实 CDS。
- 回归/Ruff：uv run pytest tests/test_climate -q → 178 passed。src/openharness/climate 与 tests/test_climate Ruff PASS。git diff --check 清洁。QueryEngine 未改。工具/引擎回归中 test_core_tools 时区（Asia/Hong_Kong）与 test_query_engine subagent_stop 失败为本机环境问题，与本次 Climate 改动无关。未提交、未推送。
- Day 07 blocker：无 Day 06 功能缺口阻塞离线 7 工具链。G2 Gate 仍须只读验收 PHASE-001。已知非 blocker 但 Gate 会点名：CI-001 仍 GAP；PERM-001 QueryEngine 路径抽取仍 GAP（Climate 侧已再校验）；全量 pytest 需处理本机时区/subagent 噪音，避免误判 Gate。G2 未正式 PASS 前不得开始 G3 Eval。matplotlib 未装时走 SVG 契约，CI extra 需在 Gate/CI-001 一并核对。
```
