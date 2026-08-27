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

## 日终报告模板

```text
Day 06 结果：
- Plot PNG/SVG：
- Report：
- 7 工具 registry：
- sample/local E2E：
- run completed 证据：
- PASS/GAP 需求：
- 回归/Ruff：
- Day 07 blocker：
```
