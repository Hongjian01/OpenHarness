# Day 05：G2-B Plan 加固与 local acquisition

## 今日目标

加固 Day 04 的 Plan 完整契约，并把最小纵切扩展为可导入本地 CSV、可验证依赖和幂等重放的
离线工作流。

- **SPEC 需求**：TOOL-PLAN-001、TOOL-ACQUIRE-001/002（local）、PATH-004、IDEM-001、PERM-001、TEST-004
- **预计投入**：6～8 小时
- **完成标志**：init → plan → acquire(sample/local) → inspect → read context 真实通过
- **上一天**：[Day 04](DAY_04_G2A_OFFLINE_VERTICAL_SLICE.md)
- **下一天**：[Day 06](DAY_06_G2B_PLOT_REPORT_PIPELINE.md)

## 严格范围

允许修改 Day 04 的 tools/pipeline/registry 和对应测试。禁止实现 plot/report/CDS/Eval。

## 开始前检查

```powershell
git status --short --branch
uv run pytest tests/test_climate -q
```

检查 Day 04 产物是否真实产生，而不是 mock：

- `.climate/index.json`
- `.climate/runs/<run_id>/context.json`
- `.climate/data/<run_id>/sample.csv`

让 Cursor 重读 SPEC 的 plan DAG、状态机、幂等和 local 普通文件限制。

## 完整开发流程

### 1. RED：Plan 完整契约（1～1.5 小时）

在 Day 04 基本成功路径上补写：

- 合法 4-step plan 的规范拓扑序。
- step_id/action/title/depends_on 严格输入。
- ID 重复、依赖不存在、自依赖、环拒绝。
- 缺少 action、report 不可达 inspect/plot 拒绝。
- 已开始业务 step 后不可替换 plan。
- plan 一次 Context mutation 完成，失败不留下部分 steps。
- plan accepted 使 run `initialized → running`。

### 2. GREEN：Plan 加固（1～1.5 小时）

补齐 DAG 校验和单次 Repository mutation。不要重写 Day 04 已通过的基本路径，不要引入通用 DAG
调度器；只满足 v0.1 plan 合同。

### 3. RED：local acquisition（1～1.5 小时）

覆盖：

- workspace 内普通 `.csv` 成功复制到 run data。
- 源文件 bytes/mtime 不变。
- 最终 artifact 与源文件不是同一路径。
- `..`、绝对路径、UNC、symlink/junction escape 拒绝。
- 目录、设备、FIFO/socket、非 CSV 拒绝。
- mode/path/cds_request 互斥。
- 前置 step 未完成时返回 dependency error。
- 同规范化输入重放不改 version/attempts。
- 不同输入重放返回 `CLIMATE_IDEMPOTENCY_CONFLICT`。

### 4. GREEN：local acquisition（1.5～2 小时）

流程固定：

1. QueryEngine 权限看到 `path`。
2. Climate 安全解析再次验证。
3. Repository/状态机将 step 标记 running。
4. 流式复制到 `.part`，flush/fsync，计算 sha256。
5. `os.replace` 发布。
6. 写 succeeded/result/artifact。
7. 失败清理 `.part` 并按 Context 可写性记录 failed。

### 5. 集成与回归（1～1.5 小时）

增加真实链路：

```text
init → plan → local acquire → inspect → read
init → plan → sample acquire → inspect → read
```

```powershell
uv run pytest tests/test_climate/test_tools.py tests/test_climate/test_pipeline.py tests/test_climate/test_registry.py -q
uv run pytest tests/test_climate -q
uv run pytest tests/test_tools/test_core_tools.py tests/test_engine/test_query_engine.py -q
uv run ruff check src/openharness/climate src/openharness/tools tests/test_climate
git diff --check
```

## 今日主 Prompt

```text
执行 ClimWorkflow Day 05 / Phase G2-B：Plan 与 local acquisition。

阅读 SPEC 第 5、8、10、13、16 节及 DAY_05_G2B_PLAN_LOCAL_ACQUIRE.md。

今日只实现 TOOL-PLAN-001、TOOL-ACQUIRE-001/002 的 local 部分、PATH-004、IDEM-001、PERM-001。

顺序：
1. 在 Day 04 基本 plan 上补写 DAG/原子性失败测试并确认 RED。
2. 最小加固 climate_plan_steps，不重写成功路径。
3. 先写 local 路径、普通文件、原子复制、依赖、幂等失败测试。
4. 最小实现 local acquisition。
5. 运行 sample/local 两条真实链路、全部 Climate 回归和 Ruff。

不得实现 plot/report/CDS/Eval，不修改 QueryEngine，不访问旧目录，不提交、不推送。
```

## 分步骤 Prompt

```text
只写 plan 失败测试。重点证明非法 DAG 和部分写入均被拒绝，不实现通用调度器。
```

```text
只写 local acquisition 安全/幂等测试。必须校验源文件未修改、最终文件独立、不同输入重放冲突。
```

```text
实现 local acquisition 的 .part→fsync→replace 流程。异常时保持最后稳定 Context，并清理本次临时文件。
```

```text
只读验收 Day 05：逐项核对 TOOL-PLAN-001、TOOL-ACQUIRE-001/002、PATH-004、IDEM-001、PERM-001。不要修复。
```

## 验收清单

- [ ] plan DAG 校验完整且原子写入。
- [ ] local 只读取 workspace 普通 CSV。
- [ ] source 不修改，artifact 独立且有摘要。
- [ ] sample/local 两条链路都真实运行。
- [ ] replay 和不同输入冲突行为符合 SPEC。
- [ ] 未实现 plot/report/CDS/Eval。

## 风险与止损

- 文件复制不得一次性无界读入内存；使用分块。
- Windows 对特殊文件能力有限时保留可运行的类型检查与平台用例。
- 如果 plan 设计需要修改已有状态机，只允许最小接口适配并重跑 G1 全量。

## 日终报告模板

```text
Day 05 结果：
- Plan 测试/实现：
- local 安全与原子复制：
- 幂等结果：
- sample/local E2E：
- PASS/GAP 需求：
- 回归与 Ruff：
- Day 06 阻塞项：
```
