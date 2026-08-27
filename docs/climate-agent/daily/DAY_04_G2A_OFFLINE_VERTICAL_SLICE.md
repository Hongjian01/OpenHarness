# Day 04：G2-A 第一条离线纵向切片

## 今日目标

在 G1 内核上完成可运行的最小工具链：

```text
init → plan → acquire(sample) → inspect(CSV) → read context
```

- **SPEC 需求**：TOOL-BASE-001、REG-001（部分）、TOOL-INIT-001、TOOL-PLAN-001、
  TOOL-ACQUIRE-001/002（sample）、TOOL-INSPECT-001、TOOL-READ-001、PERM-001、TEST-004
- **预计投入**：7～8 小时
- **完成标志**：从空 workspace 真实生成 Context、固定 sample CSV 和 inspect profile
- **上一天**：[Day 03](DAY_03_G1C_RECOVERY_STATE_MACHINE.md)
- **下一天**：[Day 05](DAY_05_G2B_PLAN_LOCAL_ACQUIRE.md)

## 开始条件

Day 03 的 G1 验收必须 PASS。若仍有 G1 GAP，停止 G2。

```powershell
git status --short --branch
uv run pytest tests/test_climate -q
```

让 Cursor 只读检查：

```text
src/openharness/tools/base.py
src/openharness/tools/__init__.py
src/openharness/engine/query.py 中 _execute_tool_call
tests/test_tools/test_core_tools.py
tests/test_engine/test_query_engine.py 中工具/权限/Hook用例
```

## 严格范围

建议新增：

```text
src/openharness/climate/tools.py
src/openharness/climate/pipeline.py
src/openharness/climate/registry.py（仅 Climate/测试内 registry，不接默认 registry）
tests/test_climate/test_tools.py
tests/test_climate/test_pipeline.py
tests/test_climate/test_registry.py
```

今日不实现 local、plot、report、CDS、Eval，不修改 QueryEngine。为避免 acquire/inspect 绕过
SPEC 的 step/依赖契约，纵向切片必须包含最小但真实的 `climate_plan_steps`。

## 完整开发流程

### 1. 冻结五个工具接口（45 分钟）

逐字段对照 SPEC 第 10 节，确认：

- Pydantic `extra="forbid"`。
- 所有结果为统一 JSON envelope。
- `climate_read_context` 为只读，其余均为 mutation。
- run_id 缺省使用 active run。
- `path` 字段参与现有权限路径提取，同时再次经过 Climate 路径验证。
- inspect 会写 Context，因此不是 read-only。

### 2. RED：registry 与 schema（45 分钟）

先写测试验证：

- 5 个今日工具名称唯一、schema 可导出。
- 输入多余字段/错误 UUID/非法 mode 被拒绝。
- 测试内独立 registry 不覆盖同名工具；REG-001 在 7 工具完成前保持 GAP。
- read-only 分类准确。

### 3. RED：纵向工具链（1.5 小时）

测试必须从空 `tmp_path` 直接调用真实工具：

1. init 创建 run、index、Context。
2. 重复 run_id 返回 `CLIMATE_RUN_EXISTS` 且不覆盖。
3. plan 原子写入合法四步 DAG，run 进入 running。
4. sample acquire 生成固定 30 行 CSV。
5. 摘要、大小、media type、相对路径进入 artifact。
6. inspect 默认使用最新 dataset，输出有界 profile。
7. inspect 不改变 dataset 的 bytes/mtime/hash。
8. read context 返回脱敏、有界视图。
9. read context 遇未完成 WAL 返回 `CLIMATE_RECOVERY_REQUIRED` 且不写文件。
10. 未 init、未 plan、非法顺序、G2 cds 请求给出稳定错误。

```powershell
uv run pytest tests/test_climate/test_registry.py tests/test_climate/test_tools.py tests/test_climate/test_pipeline.py -q
```

### 4. GREEN：最小工具实现（3 小时）

推荐顺序：

1. 工具基类辅助：统一执行边界和 JSON result。
2. init。
3. read_context。
4. plan。
5. sample acquire。
6. CSV inspect。
7. 仅接入独立 Climate/测试 registry；默认 registry 留到 Day 06 七工具齐备后一次性扩展。

所有写入必须通过 Repository；数据产物使用 `.part`/原子发布，不能让工具直接修改 Context JSON。

### 5. VERIFY（1 小时）

```powershell
uv run pytest tests/test_climate/test_registry.py tests/test_climate/test_tools.py tests/test_climate/test_pipeline.py -q
uv run pytest tests/test_climate/test_errors.py tests/test_climate/test_paths.py tests/test_climate/test_models.py tests/test_climate/test_repository.py tests/test_climate/test_state.py -q
uv run pytest tests/test_tools/test_core_tools.py tests/test_engine/test_query_engine.py -q
uv run ruff check src/openharness/climate src/openharness/tools tests/test_climate
git diff --check
git status --short
```

## 今日主 Prompt

```text
执行 ClimWorkflow Day 04 / Phase G2-A：第一条离线纵向切片。

前置：先确认 G1 验收已 PASS。阅读 SPEC 第 8～10、13、15～16 节和 DAY_04_G2A_OFFLINE_VERTICAL_SLICE.md。

只实现：
- climate_init_workflow
- climate_plan_steps
- climate_acquire_data 的 sample 模式
- climate_inspect_dataset 的 CSV 模式
- climate_read_context
- 对应 registry/schema/测试

必须先写 registry/schema/端到端失败测试并确认 RED，再最小实现。
所有写入通过安全路径、Repository、状态机和原子发布。
今日只使用独立 ToolRegistry，不修改 create_default_tool_registry；REG-001 保持 GAP。
不实现 local/plot/report/CDS/Eval，不修改 QueryEngine。
完成后运行 Climate 核心回归、工具/引擎回归和 Ruff。
不提交、不推送。
```

## 分步骤 Prompt

```text
只写五个工具的 schema、registry 和权限分类失败测试，不写工具实现。验证多余字段拒绝和同名覆盖风险。
```

```text
只写真实纵向切片测试；禁止 mock Repository 或用合成 ToolResult 假装执行成功。
```

```text
按 init → read → plan → sample acquire → CSV inspect 顺序实现最小代码。每个工具完成后运行其单测，
不提前实现 Day 05 的 local 模式。
```

```text
只读验收 Day 04：检查五工具真实副作用、原子发布、Context 版本、权限分类、默认 registry 和
QueryEngine 均无修改。输出 PASS/GAP，不修复。
```

## 验收清单

- [ ] G1 验收先通过。
- [ ] 5 个工具由真实 BaseTool 实现并可导出 schema。
- [ ] acquire/inspect 必须依赖已持久化 plan，不允许为纵切绕过状态机。
- [ ] 默认 registry 尚未加入不完整工具集，REG-001 仍为 GAP。
- [ ] sample CSV 固定、可复现、30 行。
- [ ] inspect 不修改数据文件且输出有界。
- [ ] 所有状态写入经过 Repository/状态机。
- [ ] 失败结果符合统一 envelope。
- [ ] 没有 local/plot/report/CDS/Eval。

## 风险与止损

- 若 5 工具无法在一天完成，不得删除 plan 绕过依赖契约；应顺延未完成项。inspect 不得用硬编码
  profile 伪造。
- 当前 `ToolRegistry.register` 同名覆盖，Climate 接入代码必须显式检测或测试名称无冲突。
- 不要用对话 metadata 替代持久化 Context。

## 日终报告模板

```text
Day 04 结果：
- 新增工具：
- RED 证据：
- 纵向执行产物：
- PASS/GAP 需求：
- 测试与 Ruff：
- QueryEngine diff：无/说明
- Day 05 阻塞项：
```
