# Day 13：G4 NetCDF/GRIB Inspect 与显式 Fallback

## 今日目标

将 Day 11 冻结的数据格式接入 inspect，并完成严格、可审计的显式 sample fallback。

- **SPEC 需求**：CDS-002、CDS-004、TOOL-INSPECT-001 的 G4 扩展、SEC-001/002、TEST-006
- **预计投入**：7～8 小时
- **完成标志**：格式 fixture 可被真实解析；扩展名/content 不一致拒绝；fallback 默认关闭且完整审计
- **上一天**：[Day 12](DAY_12_G4_CDS_RELIABLE_DOWNLOAD.md)
- **下一天**：[Day 14](DAY_14_G4_REAL_AGENT_BASELINE.md)

## 开始前检查

```powershell
git status --short --branch
uv run pytest tests/test_climate/test_cds.py -q
uv run pytest tests/test_climate -q
```

确认 Day 12 全部 mock 测试通过，无残留 `.part` 或凭证。

## 严格范围

只支持 Day 11 已冻结并写入 SPEC 的格式/依赖。若 SPEC 最终仅冻结 NetCDF，则不得在今天临时声称支持
GRIB。禁止真实 Agent baseline（Day 14）。

## 完整开发流程

### 1. RED：格式识别与解析（1.5 小时）

对每个冻结格式建立小型合法 fixture，测试：

- 扩展名、magic、解析器三者一致才接受。
- 正常解析变量、维度、时间、经纬坐标和基础统计。
- 缺变量、非法坐标、空时间维度、损坏/截断拒绝。
- `.nc` 装 GRIB、`.grib` 装 NetCDF、随机 bytes 拒绝。
- optional reader 缺失返回稳定依赖错误。
- profile 有界，不序列化全数据集。
- inspect 不修改数据 bytes/hash。

### 2. GREEN：Reader Adapter（2 小时）

按格式建立窄 adapter，统一返回内部 profile，不让 xarray/cfgrib 对象进入 Context。

资源要求：

- 使用 context manager/显式 close。
- 限制变量、维度和统计读取范围。
- 外部库 warning/exception 映射并脱敏。
- 不执行 dataset 内任何表达式或插件。

### 3. RED：显式 fallback（1～1.5 小时）

覆盖：

- 默认 `allow_sample_fallback=false`：CDS 失败返回原错误。
- 只有 true 且错误属于规格允许 fallback 的类别时才执行。
- fallback 成功记录：
  `requested_mode=cds`、`effective_mode=sample`、`fallback_reason=<稳定码>`。
- auth/validation/凭证错误是否允许 fallback 必须按 SPEC 冻结；不得隐式掩盖配置错误。
- Trace、Context、ToolResult 三处审计字段一致。
- fallback artifact 是有效 sample 数据，不使用损坏 `.part`。
- replay 的 input hash 包含 fallback 开关，避免语义混淆。

### 4. GREEN：Fallback 编排（1～1.5 小时）

fallback 只复用现有 sample acquisition 公共服务，不复制实现。失败原因使用稳定错误码，不保存原始
exception。requested/effective mode 写入 step result/event。

### 5. Mock 端到端与回归（1.5 小时）

链路：

```text
mock CDS NetCDF → inspect → plot → report
mock CDS 可重试失败 → 显式 sample fallback → inspect → plot → report
mock CDS 失败 + fallback false → failed，无 sample artifact
格式伪装/截断 → reject，无 artifact
```

```powershell
uv run pytest tests/test_climate/test_cds.py tests/test_climate/test_tools.py tests/test_climate/test_pipeline.py -q
uv run pytest tests/test_climate -q
uv run pytest -q
uv run ruff check src tests scripts evals
git diff --check
```

## 今日主 Prompt

```text
执行 ClimWorkflow Day 13 / Phase G4：冻结格式的 inspect 与显式 fallback。

阅读 Day 11 已更新的 SPEC 格式决策，以及 SPEC 第 6、9、10、14、16 节和
DAY_13_G4_FORMAT_INSPECTION_FALLBACK.md。

先写失败测试：
- 正常 fixture 的变量/维度/坐标/profile
- 扩展名+magic+解析器一致性
- 截断/损坏/伪装文件
- optional reader 缺失
- inspect 不修改原数据且输出有界
- 默认禁 fallback
- 显式 fallback 的 requested/effective/reason 审计

再实现窄 Reader Adapter 和 fallback 编排。
只支持已冻结格式；fallback 复用 sample 服务，不复制代码。
全部自动测试使用 fixture/mock，禁网、无凭证。
不运行真实 Agent baseline，不提交、不推送。
```

## 分步骤 Prompt

```text
只写格式 fixture 测试。测试必须让 magic 与真实 parser 都参与判断，不能只看扩展名。
```

```text
实现 reader adapter，确保关闭资源、profile 有界、外部异常脱敏，Context 不保存库对象。
```

```text
只写 fallback 测试，列出哪些稳定错误允许 fallback；未在 SPEC 冻结的错误一律不得 fallback。
```

```text
只读审查 Day 13：检查是否静默 fallback、是否掩盖 auth 错误、是否有格式伪装绕过和资源泄漏。
```

## 验收清单

- [ ] 只实现冻结格式。
- [ ] magic/content/extension/parser 一致。
- [ ] inspect profile 有界且不修改数据。
- [ ] 默认不 fallback。
- [ ] 显式 fallback 三个审计字段完整一致。
- [ ] 损坏 `.part` 不会成为 fallback 输入。
- [ ] mock 端到端和全量回归通过。

## 风险与止损

- 科学数据统计可能触发全量加载；fixture 小不代表生产安全，必须显式限制。
- GRIB backend warning 中可能含本机路径，外部输出统一脱敏。
- 如果允许 fallback 的错误集合未在 SPEC 清楚定义，先修订评审，不自行选择。

## 日终报告模板

```text
Day 13：
- 支持格式：
- fixture/parser：
- 伪装/损坏拒绝：
- inspect profile：
- fallback 默认/显式：
- 审计字段：
- mock E2E/回归：
- Day 14 前置：
```
