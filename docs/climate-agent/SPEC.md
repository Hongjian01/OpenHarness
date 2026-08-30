# ClimWorkflow 规格说明

**版本**：v0.1 Offline Engineering MVP
**状态**：G0～G3 适用需求已通过 Day 10（2026-08-28）总验收。称谓 **ClimWorkflow Offline Engineering MVP**。G4 CDS/ERA5 与真实模型 baseline 未开始（DEC-G4-001 仍开放）。

**基线日期**：2026-08-22  
**目标仓库**：`E:\agent\ClimWorkflow`（`git@github.com:Hongjian01/OpenHarness.git`）  
**开发分支**：`feat/climworkflow-mvp`  
**上游仓库**：`git@github.com:HKUDS/OpenHarness.git`  
**上游提交**：`9b2efd795c6aa09f88b0c257d269a9e518da6ae7`

## 1. 规格状态与解释规则

本文是 ClimWorkflow 在 OpenHarness 上的 Greenfield 实现契约。当前仓库在上述提交上没有
Climate 源码、Climate Eval 或 Climate 测试；除 OpenHarness 既有能力外，本文列出的所有
Climate 实现需求初始状态均为 **GAP**。

规范词“必须”“不得”“应当”只在带需求 ID 的条目中构成验收要求。发生冲突时，优先级依次为：

1. 安全、凭证和路径约束；
2. Context 持久化与状态机约束；
3. 工具输入输出契约；
4. 阶段范围和实现建议。

任何实现若需要改变契约，先修改并评审本文，不得以代码事实反向覆盖规格。

## 2. 产品目标

ClimWorkflow 是运行在 OpenHarness 工具循环中的、可恢复且可评测的气候数据工作流。它接收
一个气候分析目标，建立持久化 run，按结构化计划获取数据、检查数据、生成图表和 Markdown
报告，并允许 Agent 在会话中断或压缩后从 Context 恢复。

离线工程 MVP（G0～G3）的成功路径为：

```text
init → plan → acquire(sample/local) → inspect → plot → report → read context
```

G4 在此基础上增加真实 CDS/ERA5 获取和真实模型 smoke baseline。

## 3. 非目标

- 不构建通用 DAG 调度器、分布式队列或 Web UI。
- 不替代 OpenHarness 的 QueryEngine、权限、Hook、Memory 或 compact。
- 不允许执行用户提供的 Python、Shell、模板代码或任意表达式。
- G0～G3 不访问 CDS，不要求 API Key，不把合成 dry-run 当成真实执行。
- v0.1 不支持工作区之外的数据读取或产物写入。
- v0.1 不承诺大数据并行计算、集群执行、任意 NetCDF/GRIB 科学计算或长期存档。
- 不从旧目录 `E:\agent\OpenHarness` 迁移 Climate 源码、Eval 或测试。

## 4. 基线事实与复用边界

### 4.1 代码证据

| 能力 | 当前代码证据 | 已确认语义 |
|---|---|---|
| Agent 工具循环 | `src/openharness/engine/query.py:887-1018` | Hook → 工具查找 → Pydantic 校验 → 权限 → execute → ToolResult → Hook |
| 会话封装 | `src/openharness/engine/query_engine.py:21-59,227-305` | 注入 registry、权限、Hook、cwd、tool metadata；支持 pending continuation |
| 工具抽象 | `src/openharness/tools/base.py:17-80` | `BaseTool`、`ToolExecutionContext`、`ToolResult`、`ToolRegistry` |
| 默认注册 | `src/openharness/tools/__init__.py:48-98` | 构造默认 registry 并注册内建/MCP 工具 |
| Hook | `src/openharness/hooks/events.py:8-20`、`hooks/executor.py:41-78` | 支持 pre/post tool、compact 等事件和 matcher |
| 权限 | `src/openharness/permissions/checker.py:57-156` | 只读放行、写工具确认、plan 阻断、路径规则和敏感路径拒绝 |
| 原子写 | `src/openharness/utils/fs.py:39-77` | 同目录临时文件、flush/fsync、`os.replace`、失败清理 |
| 文件锁 | `src/openharness/utils/file_lock.py:26-86` | Windows/POSIX 阻塞式独占文件锁 |
| Settings | `src/openharness/config/settings.py:1-25,50-74` | CLI/环境/用户文件/默认值优先级；已有权限和 memory 配置 |
| Memory | `src/openharness/memory/manager.py:39-159` | 项目 memory 使用锁和原子写；不是业务 Context |
| compact | `src/openharness/services/compact/__init__.py:88-109,1119-1475` | 保留结构化摘要、附件、Hook 和 carry-over metadata |
| 测试配置 | `pyproject.toml:38-46,75-86` | pytest/asyncio、ruff、mypy 依赖与配置 |
| CI | `.github/workflows/ci.yml:9-60` | Python 3.10/3.11 全量 pytest；Python 3.11 ruff |

当前 `exclusive_file_lock` 不提供超时；当前 `POST_TOOL_USE` 的 blocked 结果不会撤销已执行工具。
因此 v0.1 使用阻塞锁，所有强制输出路径防护在工具执行前完成；G3 的 Hook guard 使用
`PRE_TOOL_USE`，不把 post hook 视为回滚边界。

### 4.2 REUSE / EXTEND / NEW 矩阵

| 分类 | 能力 | v0.1 决策 | 状态 |
|---|---|---|---|
| REUSE | `QueryEngine` / `run_query` | 原样承载 Climate 工具，不建立第二套 Agent loop | 已存在 |
| REUSE | `BaseTool` / `ToolResult` / `ToolExecutionContext` | 所有 Climate 工具实现该接口 | 已存在 |
| REUSE | `ToolRegistry` | 注册和 API Schema 导出 | 已存在 |
| EXTEND | `create_default_tool_registry` | G2 注册 7 个 Climate 工具；不改变 registry 语义 | PASS |
| REUSE | Pydantic v2 | 工具输入和持久化模型校验 | 已存在 |
| REUSE | `PermissionChecker` | 根据 `is_read_only` 控制写工具；路径参数统一命名为 `path` 以参与路径规则 | 已存在 |
| EXTEND | `SENSITIVE_PATH_PATTERNS` | G4 将 `.cdsapirc` 加入不可覆盖的敏感路径拒绝规则 | GAP |
| REUSE | `HookExecutor` / 事件 | G3 采集轨迹并以前置 Hook 演示输出路径 guard | 已存在 |
| REUSE | `atomic_write_text` | Context、索引、事务标记、报告文本的原子替换 | 已存在 |
| REUSE | `exclusive_file_lock` | workspace/run 读改写临界区 | 已存在 |
| REUSE | Memory / compact | 保持会话连续性；不保存权威 Climate 状态 | 已存在 |
| EXTEND | Python optional dependencies | G2 可选 matplotlib；G4 可选 cdsapi 和科学数据读取依赖 | PASS (G2 matplotlib extra `plot`) |
| EXTEND | README / Skill | G3 增加可复现离线演示与 `climate-ds` Skill | PASS (Day 09：README 空 workspace Demo；`.openharness/skills/climate-ds/SKILL.md`) |
| NEW | `src/openharness/climate/` | 路径、模型、仓储、状态机、流水线和工具 | PASS（G1～G3：`errors`/`paths`/`models`/`repository`/`state`/`tools`/`pipeline`/`registry`）；Skill 为项目级 `.openharness/skills/climate-ds`；CDS GAP |
| NEW | `.climate/` workspace state | run Context、数据、产物、锁、事务和备份 | PASS（G1 布局/Context/index/锁/事务/备份；G2 sample/local CSV、inspect profile、plot、report.md） |
| NEW | `tests/test_climate/` | Climate 单元、契约、集成和安全测试 | PASS（G1～G3；Day 10 collect 198 Climate + 2 Skill）；G4 `test_cds.py` GAP |
| NEW | `evals/` Climate suite | scenario、trace、runner、硬断言和 baseline | PASS（G3 四场景 real_offline + synthetic_dry_run）；real_agent baseline GAP |

### 4.3 基线要求

- **BASE-001（MUST，G0，PASS）**：实现和文档必须绑定本规格页首的目标仓库、分支和上游提交；
  上游变更后先重新评审复用矩阵。
- **BASE-002（MUST，G0，PASS）**：任何 Climate 功能在自动化测试通过前都保持 GAP；不得沿用旧
  PoC 的完成声明或测试结果。
- **ARCH-001（MUST，G1～G3，PASS）**：G1～G3 不得为 Climate 修改 QueryEngine 的执行语义；
  Climate 状态通过工具、Context Repository 和现有 tool metadata 边界接入。
  （Day 07 验收：`query.py`/`query_engine.py` 无 Climate diff；PERM-001 经现有 `_execute_tool_call` 接入。）

## 5. 工作区布局与安全路径

### 5.1 固定布局

```text
<workspace>/
  .climate/
    index.json
    runs/
      <run_id>/context.json
    data/
      <run_id>/...
    output/
      <run_id>/...
    locks/
      workspace.lock
      <run_id>.lock
    transactions/
      active-run-<transaction_id>.json
    backups/
      <run_id>-context-v<old>-<utc_timestamp>.json
```

`workspace` 是 `ToolExecutionContext.cwd.resolve()`。Context 中所有路径使用相对 workspace 的
POSIX 形式；输出不得暴露本机绝对路径。

### 5.2 路径要求

- **PATH-001（MUST，G1，PASS）**：所有用户路径只接受非空、workspace 相对路径；拒绝绝对路径、
  drive-relative 路径、UNC、`~`、空段、`.`/`..`、NUL、混合分隔符绕过和 Windows 保留设备名。
- **PATH-002（MUST，G1，PASS）**：解析器必须在访问前按真实路径验证目标仍位于 workspace；
  已存在父链中的 symlink/junction 不得逃逸。平台无法可靠验证时必须拒绝，而不是放行。
- **PATH-003（MUST，G1～G2，PASS）**：Climate 内部写入仅允许固定区域：
  acquisition 写 `.climate/data/<run_id>/`，plot/report 写 `.climate/output/<run_id>/`，
  Context 基础设施写第 5.1 节固定状态路径。
- **PATH-004（MUST，G2，PASS）**：local acquisition 只能读取 workspace 内普通文件；不得读取
  目录、设备、FIFO/socket，且不得原地修改源文件。
- **SEC-001（MUST，G1～G4，PASS）**：错误、日志、ToolResult、Context 和 Trace 不得包含用户主
  目录、workspace 绝对路径、API key、CDS token、`.cdsapirc` 内容或完整凭证异常文本。
  （G1 已由路径/错误脱敏测试覆盖；G2 report Markdown 脱敏已覆盖；G3 Eval Trace 密钥扫描已由
  `test_evals.py::test_trace_record_requires_section_12_fields_and_redacts_input` 覆盖。）
- **SEC-002（MUST，G4，GAP）**：CDS 凭证只由 cdsapi 的标准外部配置读取；Climate 输入模型、
  Context、Eval fixture 和仓库文件不得接收或持久化凭证；`.cdsapirc` 必须加入
  `SENSITIVE_PATH_PATTERNS`，在全部权限模式下阻止通用工具读取。

## 6. Context Schema

### 6.1 通用规则

- JSON 编码为 UTF-8、两空格缩进、键顺序稳定、文件末尾换行。
- 时间为 UTC RFC 3339（例如 `2026-08-22T14:00:00Z`）。
- `run_id` 和 `transaction_id` 是规范小写 UUID v4。
- `version` 是每次成功 Context 修改后严格递增的正整数；创建值为 1。
- 当前 run schema 为 `schema_version: 2`；workspace index schema 为 1。
- 未知顶层字段和无效 enum 一律拒绝，防止静默丢失数据。

### 6.2 WorkspaceIndex

```json
{
  "schema_version": 1,
  "version": 3,
  "active_run_id": "0e8e6eb4-93f2-4ce7-8d22-91a28fa99314",
  "run_ids": ["0e8e6eb4-93f2-4ce7-8d22-91a28fa99314"],
  "updated_at": "2026-08-22T14:00:00Z"
}
```

`active_run_id` 可为 `null`；`run_ids` 去重并按创建时间排列。

### 6.3 RunContext v2

```json
{
  "schema_version": 2,
  "version": 4,
  "run_id": "0e8e6eb4-93f2-4ce7-8d22-91a28fa99314",
  "objective": "分析示例温度序列并生成报告",
  "status": "running",
  "created_at": "2026-08-22T14:00:00Z",
  "updated_at": "2026-08-22T14:03:00Z",
  "steps": [
    {
      "step_id": "acquire",
      "action": "acquire_data",
      "title": "获取数据",
      "depends_on": [],
      "status": "succeeded",
      "attempts": 1,
      "input_hash": "sha256:...",
      "started_at": "2026-08-22T14:01:00Z",
      "finished_at": "2026-08-22T14:01:01Z",
      "result": {"artifact_ids": ["data-primary"]},
      "error": null
    }
  ],
  "artifacts": [
    {
      "artifact_id": "data-primary",
      "kind": "dataset",
      "path": ".climate/data/0e8e6eb4-93f2-4ce7-8d22-91a28fa99314/sample.csv",
      "media_type": "text/csv",
      "size_bytes": 120,
      "sha256": "sha256:...",
      "created_by_step": "acquire",
      "created_at": "2026-08-22T14:01:01Z"
    }
  ],
  "events": [
    {
      "sequence": 1,
      "timestamp": "2026-08-22T14:00:00Z",
      "type": "run_created",
      "step_id": null,
      "data": {}
    }
  ],
  "last_error": null
}
```

固定枚举如下：

- `RunContext.status`：`initialized | running | completed | failed`。
- `Step.action`：`acquire_data | inspect_dataset | analyze_plot | write_report`。
- `Step.status`：`pending | running | succeeded | failed | skipped`。
- `Artifact.kind`：`dataset | profile | plot | report`。
- `Event.type`：`run_created | active_run_changed | plan_created | step_started |
  step_succeeded | step_failed | step_skipped | run_completed | run_failed | run_resumed |
  migration_completed | interrupted_recovered`。

`Step.error` 和 `last_error` 为 `null` 或第 9 节 error 对象
`{code, message, retryable, details}`，并遵循同一脱敏规则。`result` 和 event `data` 只允许
JSON 值，不存放大块数据、外部库对象或绝对路径。

标准演示 plan 恰好包含 acquire、inspect、plot、report 四个 step。一般 v0.1 plan 允许 4～32
个 step、允许同一 action 出现多次，但四类 action 各至少一次；依赖必须组成无环图，且每个
report 都必须可达至少一个 inspect 和一个 plot。

### 6.4 Context 要求

- **CTX-001（MUST，G1，PASS）**：WorkspaceIndex 和 RunContext 必须按本节严格校验、确定性序列化，
  并维持 `schema_version`、`version`、时间、唯一 ID、事件 sequence 和 artifact 引用一致性。
- **CTX-002（MUST，G1/G3，PASS）**：权威业务状态只能位于第 5.1 节 Context；对话、Memory、compact
  summary 和 ToolResult 都不是权威状态。（G1 新 Repository 读盘 PASS；G3 多轮重启
  `multiturn_recovery` PASS；Day 09 Skill 强制先 `climate_read_context`、禁止 compact/猜测：
  `tests/test_skills/test_climate_skill.py::test_climate_skill_frontmatter_and_guidance`。）
- **CTX-003（MUST，G1，PASS）**：读取失败必须稳定区分三类错误码：run 不存在返回
  `CLIMATE_RUN_NOT_FOUND`，schema 版本不兼容返回 `CLIMATE_SCHEMA_UNSUPPORTED`，无效 JSON 或
  schema 内语义不一致返回 `CLIMATE_CONTEXT_CORRUPT`；后两者可用安全 `details.reason`
  区分 `invalid_json | invalid_semantics`。任何失败都不得用空 Context 覆盖原文件。
- **MIG-001（MUST，G1，PASS）**：Repository 必须支持 fixture 定义的 RunContext v1→v2 单步迁移；
  在持有锁时先把原始字节原子写入 `backups/`，再写 v2。迁移幂等，备份失败则中止迁移。

v1 fixture 与 v2 相同，但没有 `events[*].sequence` 和 Artifact 的 `sha256`；迁移按原顺序从 1
补 sequence，并计算现存 workspace 内 artifact 的 sha256。artifact 缺失时迁移以
`CLIMATE_MIGRATION_FAILED` 失败，不猜测摘要。

## 7. 持久化、锁、并发与恢复

### 7.1 原子写和锁顺序

所有 JSON/Markdown 文本状态写入复用 `atomic_write_text`。二进制下载或图像先写同目录
`.<name>.<uuid>.part`，完成 flush/fsync、格式检查和摘要计算后用 `os.replace` 发布。

需要两把锁时固定顺序如下：

```text
workspace.lock → <run_id>.lock → 读 → expected_version 校验 → 写 → 逆序释放
```

只访问单 run 且不改变 index 时仅持有 run lock。任何代码不得先持有 run lock 再请求
workspace lock。

- **IO-001（MUST，G1～G4，PASS/GAP）**：Context、index、事务、迁移备份和最终文本产物必须原子发布；
  失败后保留最后稳定文件并清理本次临时文件。（G1 Context/index/WAL/备份 PASS；G2 sample CSV、
  inspect profile、plot 图像与 report.md PASS；G4 下载仍 GAP。）
- **LOCK-001（MUST，G1，PASS）**：所有共享状态读改写必须使用现有 `exclusive_file_lock`，遵守固定
  锁序；并发测试不得出现丢失更新或死锁。
- **CON-001（MUST，G1，PASS）**：每个 mutation 接受内部 `expected_version`；不匹配时返回
  `CLIMATE_VERSION_CONFLICT`，不写文件、不自动覆盖、不隐式重试业务操作。

### 7.2 active run 事务

创建或切换 active run 使用 write-ahead marker：

1. 持有 workspace lock，并为目标 run 按固定顺序持有 run lock；
2. 原子写 `transactions/active-run-<transaction_id>.json`，记录 `old_active_run_id`、
   `new_active_run_id`、`run_context_written`、`index_written`；
3. 创建/验证 run Context，更新并原子写 marker；
4. 更新 index，更新并原子写 marker；
5. 删除 marker；删除失败可留待恢复。

启动任何 **mutating** Climate 工具时先在 workspace lock 下恢复事务。恢复按文件事实完成或回滚：
有效的新 run Context 存在时补写 index；不存在时恢复旧 active pointer。index 未引用但存在的
有效 run 是 orphan，只能通过显式 `resume_run_id` 恢复，不能自动选择“最新”。

`climate_read_context` 的权限分类必须保持纯只读：它不得迁移 schema、完成/回滚 WAL 或删除
marker。若检测到未完成 active-run marker，返回 `CLIMATE_RECOVERY_REQUIRED`；用户随后调用
mutating 的 `climate_init_workflow`（含显式 `resume_run_id`）或其他 mutation 触发恢复，再重试读取。

- **REC-001（MUST，G1，PASS）**：损坏 Context/Index 必须保持原字节不变并返回
  `CLIMATE_CONTEXT_CORRUPT`；若 Context 不可写，不得尝试二次写入 `last_error`。
- **REC-002（MUST，G1，PASS）**：active-run 事务必须可在每个故障注入点重复恢复；重复恢复幂等，
  不得产生两个 active run。
- **REC-003（MUST，G1，PASS）**：恢复必须列出 orphan run；只有 init 的 `resume_run_id` 可激活
  指定且有效的 orphan，目标不存在、损坏或已 active 时返回确定结果。

## 8. 状态机与幂等

### 8.1 Run 状态

| 当前 | 事件 | 下一状态 | 条件 |
|---|---|---|---|
| `initialized` | plan accepted | `running` | plan 合法 |
| `running` | report succeeded | `completed` | 所有非 skipped step succeeded |
| `initialized`/`running` | fatal workflow failure | `failed` | Context 仍可写 |
| `failed` | explicit retry/resume | `running` | 错误可恢复且 plan 有未成功 step |
| `completed` | read/replay | `completed` | 只读或同输入幂等 replay |

其他转换返回 `CLIMATE_INVALID_TRANSITION`。

### 8.2 Step 状态

| 当前 | 事件 | 下一状态 | attempts |
|---|---|---|---|
| `pending` | start | `running` | +1 |
| `failed` | retry | `running` | +1 |
| `running` | success | `succeeded` | 不变 |
| `running` | operation error | `failed` | 不变 |
| `pending` | explicit plan skip | `skipped` | 不变 |
| `succeeded` | same normalized input replay | `succeeded` | 不变 |

`running` 是已持久化的意图边界。进程恢复时，残留 `running` step 转为 `failed`，错误码为
`CLIMATE_INTERRUPTED`，清理该 step 的 `.part` 文件；不得推断外部副作用已经成功。

- **STATE-001（MUST，G1，PASS）**：状态机（经 Repository 持久化）必须只允许上述 run/step 转换；
  非法转换不改变版本、时间、事件或文件。
- **STATE-002（MUST，G1，PASS）**：attempts 只在进入 `running` 时递增；每次转换追加连续 sequence
  的 event，并保持最后稳定状态可读取。
- **STATE-003（MUST，G1，PASS）**：操作异常必须结构化记录到 step.error；仅当 Context 可写时更新
  Context，写入失败时直接返回原始持久化错误，不递归记录错误。
- **IDEM-001（MUST，G1～G2，PASS）**：成功 step 以规范化输入的 SHA-256 作为幂等键；同输入
  replay 返回已存结果且不改版本，不同输入返回 `CLIMATE_IDEMPOTENCY_CONFLICT`。（G1 状态机
  PASS；G2 工具层 sample/local/plot/report replay PASS。）

## 9. 错误模型

所有 Climate 工具把 `ToolResult.output` 编码为单个确定性 JSON 对象；`ToolResult.is_error` 与
`ok` 互为反值。成功：

```json
{"ok":true,"data":{},"run_id":"...","context_version":4}
```

失败：

```json
{
  "ok": false,
  "error": {
    "code": "CLIMATE_INVALID_PATH",
    "message": "路径不符合 workspace 安全策略",
    "retryable": false,
    "details": {}
  },
  "run_id": null,
  "context_version": null
}
```

固定错误码：

| 错误码 | retryable | 含义 |
|---|---:|---|
| `CLIMATE_INVALID_INPUT` | false | Pydantic 之后的跨字段/语义错误 |
| `CLIMATE_INVALID_PATH` | false | 路径或文件类型不安全 |
| `CLIMATE_RUN_NOT_FOUND` | false | run 不存在 |
| `CLIMATE_RUN_EXISTS` | false | run_id 重复且未显式 resume |
| `CLIMATE_CONTEXT_CORRUPT` | false | JSON/schema/语义损坏 |
| `CLIMATE_SCHEMA_UNSUPPORTED` | false | 不支持的 schema 版本 |
| `CLIMATE_MIGRATION_FAILED` | false | 迁移或备份失败 |
| `CLIMATE_LOCK_FAILED` | true | 平台锁不可用或锁操作失败 |
| `CLIMATE_WRITE_FAILED` | true | 原子写/替换失败 |
| `CLIMATE_VERSION_CONFLICT` | true | 乐观版本冲突 |
| `CLIMATE_INVALID_TRANSITION` | false | run/step 顺序不合法 |
| `CLIMATE_DEPENDENCY_NOT_READY` | false | step 前置依赖未成功 |
| `CLIMATE_IDEMPOTENCY_CONFLICT` | false | 成功 step 被不同输入重放 |
| `CLIMATE_INTERRUPTED` | true | 恢复到未完成 running step |
| `CLIMATE_RECOVERY_REQUIRED` | true | 只读调用发现待恢复事务，需先执行受权限控制的 mutation |
| `CLIMATE_FORMAT_UNSUPPORTED` | false | 数据格式不支持 |
| `CLIMATE_DEPENDENCY_MISSING` | false | 可选 Python 依赖缺失且无降级 |
| `CLIMATE_DATA_INVALID` | false | 数据内容/格式校验失败 |
| `CLIMATE_EXTERNAL_TIMEOUT` | true | 允许重试的 CDS timeout |
| `CLIMATE_EXTERNAL_RATE_LIMIT` | true | 允许重试的 CDS rate limit |
| `CLIMATE_EXTERNAL_FAILED` | false | 其他 CDS 错误 |
| `CLIMATE_HOOK_BLOCKED` | false | 前置 Hook 阻断 |

`CLIMATE_HOOK_BLOCKED` 是 Eval Trace 的规范化错误码。由于现有 `PRE_TOOL_USE` 在 Climate 工具
执行前由 QueryEngine 直接返回 ToolResultBlock，该原始阻断结果不受 Climate ToolResult envelope
约束；不得为统一 envelope 修改 QueryEngine 语义。

- **ERR-001（MUST，G1～G4，PASS/GAP）**：所有 Climate 失败必须遵循统一 envelope、稳定错误码和
  `is_error` 一致性；不得把 Python traceback 当成工具输出。
  （G1 共享错误基础 PASS；G2 七工具 ToolResult 一致性 PASS；G3 Foundation synthetic
  Trace 不含 traceback/密钥 PASS；Day 08 真实离线 Trace PASS；Day 09 Hook Trace
  `CLIMATE_HOOK_BLOCKED` provenance PASS。）
- **ERR-002（MUST，G1～G4，PASS）**：message 面向用户且经过脱敏；details 只含字段名、相对路径、
  状态和允许值等安全诊断信息。

## 10. 工具契约

### 10.1 共同行为

7 个工具均继承 `BaseTool`，输入模型 `extra="forbid"`。除 `climate_read_context` 外均返回
`is_read_only=False`；即使 inspect 不修改数据文件，它会写 step 结果和事件，仍是 mutation。
`run_id` 省略时使用 index 的 active run，不存在 active run 则返回 `CLIMATE_RUN_NOT_FOUND`。

- **TOOL-BASE-001（MUST，G2，PASS）**：7 个工具必须使用 Pydantic 输入、统一 JSON ToolResult、
  Repository、状态机和安全路径解析器；不得直接对 Context 使用 `Path.write_text`。
- **REG-001（MUST，G2，PASS）**：`create_default_tool_registry()` 必须恰好各注册一个下列名称的工具，
  schema 可被 `to_api_schema()` 导出，且不得覆盖同名既有工具。G2 中途纵切测试使用独立
  `ToolRegistry` 手工注册当前工具；只有 7 个工具全部实现后才一次性扩展默认 registry，禁止
  把不完整工具集分批加入默认 registry。

### 10.2 `climate_init_workflow`

输入：

```json
{
  "objective": "非空，1～4000 字符",
  "run_id": "可选 UUID v4",
  "resume_run_id": "可选 UUID v4"
}
```

`run_id` 与 `resume_run_id` 互斥。新建时创建 RunContext 并切换 active run；resume 时 objective
必须省略，只激活显式 orphan。输出包含 run 摘要和相对 Context 路径。

- **TOOL-INIT-001（MUST，G2，PASS）**：init 必须实现新建、重复 run_id 拒绝和显式 orphan resume，
  并使用 active-run 事务；不得覆盖已有 run。

### 10.3 `climate_plan_steps`

输入：

```json
{
  "run_id": "可选 UUID v4",
  "steps": [
    {
      "step_id": "1～64 字符，小写字母/数字/连字符",
      "action": "acquire_data | inspect_dataset | analyze_plot | write_report",
      "title": "1～200 字符",
      "depends_on": ["step_id"]
    }
  ]
}
```

steps 为 4～32 项；四类 action 各至少出现一次，允许同一 action 多 step；ID 唯一、依赖存在、
图无环，每个 report 依赖可达 inspect 与 plot。标准演示使用恰好四个 step。输出为规范拓扑顺序。

- **TOOL-PLAN-001（MUST，G2，PASS）**：plan 必须验证完整性和 DAG，在一次 Context mutation 中
  持久化；已开始业务 step 后不得替换 plan。

### 10.4 `climate_acquire_data`

输入：

```json
{
  "run_id": "可选 UUID v4",
  "step_id": "plan 中 acquire_data step",
  "mode": "sample | local | cds",
  "path": "local 模式 workspace 相对源路径，否则禁止",
  "cds_request": "仅 cds 模式，见第 14 节"
}
```

sample 生成固定 CSV：`date,temperature_c,precipitation_mm`，固定 30 行、UTC 日期、UTF-8/LF；
local 复制允许的 `.csv` 到 run data 目录并计算摘要，禁止引用原文件作为最终 artifact。

- **TOOL-ACQUIRE-001（MUST，G2，PASS）**：sample/local 必须离线、确定性地产生独立 dataset
  artifact，原子发布并记录 media type、大小和 sha256。
- **TOOL-ACQUIRE-002（MUST，G2，PASS）**：mode 与 path/cds_request 必须严格互斥；G2 的 cds
  请求返回 `CLIMATE_FORMAT_UNSUPPORTED`，不得静默降级为 sample。

### 10.5 `climate_inspect_dataset`

输入：

```json
{
  "run_id": "可选 UUID v4",
  "step_id": "plan 中 inspect_dataset step",
  "path": "可选；默认使用本 run 最近的 dataset artifact"
}
```

G2 支持 CSV。结果包含 `row_count`、列名、推断 dtype、每列 null count、数值 min/max/mean 和最多
20 条 validation warning。读取有界：文件最大 50 MiB，统计流式或分块，结果不得包含原始全表。

- **TOOL-INSPECT-001（MUST，G2，PASS）**：inspect 不得修改 dataset；必须验证依赖、格式、大小和
  schema，确定性写入有界 profile 结果与事件。（G2-A CSV 模式 PASS。）

### 10.6 `climate_analyze_plot`

输入：

```json
{
  "run_id": "可选 UUID v4",
  "step_id": "plan 中 analyze_plot step",
  "path": "可选；默认使用本 run dataset artifact",
  "chart_type": "line | bar | histogram",
  "x": "可选列名",
  "y": "目标列名",
  "title": "可选，最多 200 字符"
}
```

line/bar 需要 x、y；histogram 只使用 y。优先用 matplotlib 生成 PNG；依赖不存在时用标准库生成
确定性 SVG。两种路径都必须产生真实可打开的图，不允许写占位文本。

- **TOOL-PLOT-001（MUST，G2，PASS）**：plot 必须仅从已检查 dataset 读取、验证列和数值类型，只写
  run output 目录，并记录实际 media type、sha256 和降级原因。

### 10.7 `climate_write_report`

输入：

```json
{
  "run_id": "可选 UUID v4",
  "step_id": "plan 中 write_report step",
  "title": "1～200 字符",
  "summary": "1～12000 字符"
}
```

报告是 UTF-8 Markdown，包含目标、数据来源模式、inspect 摘要、图表相对链接、用户 summary、
run_id 和生成时间；不得把 summary 当模板执行，也不得嵌入绝对路径。

- **TOOL-REPORT-001（MUST，G2，PASS）**：report 必须验证所有依赖成功，原子写
  `.climate/output/<run_id>/report.md`，记录 artifact，并在全部 step 完成时把 run 标记 completed。

### 10.8 `climate_read_context`

输入：

```json
{
  "run_id": "可选 UUID v4",
  "include_events": false,
  "event_limit": 100
}
```

`event_limit` 范围 1～1000，默认只返回最近事件；输出为经脱敏的 Context 视图和 orphan run IDs，
不修改任何文件。迁移只可由 G1 Repository 显式 API 或其他 mutating 工具执行；read_context
遇到 v1 返回 `CLIMATE_SCHEMA_UNSUPPORTED`，遇到未完成 WAL 返回
`CLIMATE_RECOVERY_REQUIRED`，并提示先执行受权限控制的恢复 mutation。

- **TOOL-READ-001（MUST，G2，PASS）**：read_context 必须是文件系统和业务状态均只读、输出有界并
  支持从 active 或指定 run 恢复；不得迁移/恢复事务，不得返回 marker 内容、锁文件、备份内容或
  绝对路径。

## 11. OpenHarness 集成契约

- **PERM-001（MUST，G2，PASS）**：只有 `climate_read_context` 的 `is_read_only()` 返回 true；
  其余工具服从 OpenHarness default/plan/full_auto 权限语义。含 `path` 的调用必须让 QueryEngine
  现有路径提取参与权限检查，同时 Climate 自身再次执行 PATH 校验。
  （G2-A/B 只读分类、`path` 字段与 Climate 再校验（含 local）PASS；Day 07 默认 registry +
  QueryEngine `_execute_tool_call` 路径规则阻断 PASS。）
- **HOOK-001（MUST，G3，PASS）**：Eval 必须证明 matcher 命中的 `PRE_TOOL_USE` Hook 可在
  Climate 工具 execute 前阻断并产生轨迹；工具未执行、Context 版本和文件系统均不变化。
  （Day 09：`tests/test_climate/test_evals.py::test_pre_tool_output_guard_blocks_before_execute`；
  `::test_real_offline_scenarios_and_hook_provenance`；`::test_cli_real_offline_runs_core_scenarios`。
  真实 HookExecutor Command Hook 阻断 `climate_write_report`；execute=0；Context/文件树零变化；
  错误码 `CLIMATE_HOOK_BLOCKED`。）
- **MEM-001（MUST，G3，PASS）**：会话压缩或重启后的恢复必须调用 `climate_read_context` 获取权威
  状态；Skill 不得依赖 compact summary 猜测 run/step 成功。
  （Day 08：多轮重启只从磁盘 Context 恢复 PASS；Day 09：`climate-ds` Skill 强制先
  `climate_read_context`，禁止 compact/猜测成功。）
- **SKILL-001（MUST，G3，PASS）**：`climate-ds` Skill 必须指导 Agent 遵循工具顺序、错误码、
  恢复和禁止凭证泄露规则，并能被现有 Skill loader 从项目级
  `.openharness/skills/climate-ds/SKILL.md` 加载。
  （Day 09：`tests/test_skills/test_climate_skill.py::test_climate_skill_loads_from_project_directory`；
  `::test_climate_skill_frontmatter_and_guidance`。）

## 12. Eval 契约

### 12.1 Scenario 与 TraceRecord

`evals` 是 G3 新模块。Scenario 至少包含：

```text
id, description, mode(real_offline|synthetic_dry_run|real_agent), initial_files,
turns, expected_tool_sequence, hard_assertions, timeout_seconds
```

`real_agent` 枚举在 G3 可以被 schema 识别，但 runner 必须以
`CLIMATE_DEPENDENCY_MISSING`/明确“G4 尚未配置”拒绝执行；只有 G4 完成固定模型 adapter 后才可运行，
不得在 G3 计入任何通过率。

每条 TraceRecord 至少包含：

```text
suite_version, scenario_id, run_id, mode, started_at, finished_at,
duration_ms, tool_calls[{sequence,name,input_redacted,is_error,error_code,duration_ms}],
hook_events[{sequence,event,tool_name,blocked,reason_code}],
final_run_status, final_context_version, artifact_manifest, assertion_results
```

### 12.2 必备场景

1. `sample_pipeline`：真实离线执行完整 sample 流水线；
2. `cached_inspect`：使用 fixture CSV 执行 local acquire + inspect；
3. `multiturn_recovery`：新会话只凭 workspace Context 恢复并继续；
4. `pre_tool_output_guard`：前置 Hook 拒绝不合规 write_report 调用，证明 execute 未发生。

- **EVAL-001（MUST，G3，PASS）**：runner 必须输出上述 TraceRecord，硬断言工具序列、错误码、最终
  状态、Context 版本、artifact 存在性/摘要和 Hook 事件；任一硬断言失败时进程非零退出。
  （Day 07 Foundation PASS；Day 08 三核心场景真实离线硬断言 PASS；Day 09 Hook 事件硬断言 PASS。）
- **EVAL-002（MUST，G3，PASS）**：前三个核心场景必须使用真实 Climate 工具离线执行；Hook 场景
  必须由 Hook 阻断而不是工具自身校验拒绝。
  （Day 08：`sample_pipeline`/`cached_inspect`/`multiturn_recovery` PASS；Day 09：
  `pre_tool_output_guard` 经 HookExecutor 阻断，非 Pydantic/路径校验。）
- **EVAL-003（MUST，G3，PASS）**：synthetic dry-run 只能验证 scenario 解析、断言 wiring 和报告
  格式；输出必须显著标记 synthetic，且不得计入真实工具或模型通过率。

## 13. 测试与 CI 契约

- **SDD-001（MUST，G1～G4，PASS）**：每个实现需求先增加会失败的自动化测试，再写最小实现；
  阶段验收保留需求 ID 到测试 node ID 的映射。（G1-A/B/C、G2-A/B Day 04～06、Day 07 Eval
  Foundation、Day 08 real_offline 三场景、Day 09 Hook/Skill/README 已执行 RED→GREEN
  并回填 node ID。）
- **TEST-001（MUST，G1，PASS）**：路径测试覆盖正常相对路径、`..`、绝对/drive-relative、混合
  分隔符、UNC、symlink/junction 逃逸和错误脱敏。
- **TEST-002（MUST，G1，PASS）**：Repository 测试覆盖原子写故障注入、锁顺序/并发、版本冲突、
  重复 run_id、损坏 JSON、v1 迁移备份和 active-run 每个故障点恢复。
- **TEST-003（MUST，G1，PASS）**：状态机测试参数化覆盖所有合法/非法转换、attempts、幂等 replay、
  中断恢复和 Context 不可写。
- **TEST-004（MUST，G2，PASS）**：工具测试覆盖每个 Pydantic schema、成功/失败 envelope、非法
  顺序、权限只读分类、registry、local 目录/设备/FIFO/socket 拒绝和完整 sample/local 端到端。
  （G2-A 五工具、G2-B local、G2-B Day 06 plot/report 与默认 registry、Day 07
  QueryEngine 路径阻断均 PASS。）
- **TEST-005（MUST，G3，PASS）**：Eval 测试覆盖四个场景、synthetic 标记、硬断言失败退出和
  Trace 脱敏；真实离线场景不得请求网络。
  （Day 07 Foundation PASS；Day 08 三核心真实离线 + 禁网 PASS；Day 09 Hook 场景与 README
  Demo smoke PASS。`test_evals.py` 19 项。）
- **TEST-006（MUST，G4，GAP）**：CDS 单元测试使用 mock，真实网络测试带
  `pytest.mark.climate_integration`，该 marker 必须在 `pyproject.toml` 注册且默认 CI 跳过。
- **CI-001（MUST，G1～G4，PASS/GAP）**：每阶段至少通过受影响 Climate 测试、`uv run ruff check
  src tests scripts evals`（目录存在后）和必要 OpenHarness 回归；G2 起全量 `uv run pytest -q`
  在 Python 3.10/3.11 CI 通过。
  （Day 10：`uv run pytest tests/test_climate --collect-only -q` 198 tests；本机
  `uv run pytest tests/test_climate -q` 198 passed in 52.29s；`uv run ruff check src tests
  scripts evals` PASS；`uv run python -m evals --suite climate --mode real_offline` 4/4、
  `real_pass_rate=1.0`。GitHub Actions 未推送故无远程证据；本机 Windows 上 OpenHarness
  若干 POSIX/时区/符号链接/cmd 失败不计入 Climate 回归。）

## 14. G4：CDS / ERA5 契约

`cds_request` 输入：

```json
{
  "dataset": "reanalysis-era5-single-levels",
  "variables": ["2m_temperature"],
  "area": [90.0, -180.0, -90.0, 180.0],
  "date_start": "2025-01-01",
  "date_end": "2025-01-31",
  "format": "netcdf",
  "allow_sample_fallback": false
}
```

area 顺序为 north, west, south, east；经纬度有界且 north > south。日期为闭区间、start ≤ end，
最长 366 天。dataset/variables 使用显式 allowlist；format 为 `netcdf | grib`。

- **CDS-001（MUST，G4，GAP）**：G4 必须验证 dataset、variables、area、日期和 format；cdsapi
  为 optional dependency，缺失时返回稳定错误。
- **CDS-002（MUST，G4，GAP）**：下载必须使用 `.part`，校验非空、magic/content 与扩展名一致后
  原子替换；失败清理临时文件，不发布 artifact。
- **CDS-003（MUST，G4，GAP）**：只对 timeout/rate-limit 做有界指数退避，最多 3 次；其他错误
  不重试。默认不得 fallback。
- **CDS-004（MUST，G4，GAP）**：仅当 `allow_sample_fallback=true` 时可显式 fallback，并记录
  `requested_mode`、`effective_mode`、`fallback_reason`；只有耗尽重试后的
  `CLIMATE_EXTERNAL_TIMEOUT` 或 `CLIMATE_EXTERNAL_RATE_LIMIT` 允许 fallback，认证、输入、依赖、
  格式、路径、写入和其他 external failure 一律不得 fallback。错误和记录均须脱敏。
- **MODEL-001（MUST，G4，GAP）**：固定 provider/model/config 的真实 Agent smoke 连续运行 3 次，
  至少 2 次满足全部硬断言才可写 baseline；baseline 记录配置、提交、时间、各次结果和非敏感耗时。

G4 固定入口为：

```powershell
uv run python -m evals --suite climate --mode real_agent `
  --agent-config evals/configs/climate-real.json `
  --runs 3 `
  --baseline-out evals/baselines/climate-real-<commit>.json
```

`agent-config` 只能保存非敏感 provider/profile/model/effort/max_turns/scenario 引用，凭证继续由
OpenHarness 外部配置解析。任一次修改代码、commit、config 或 scenario 后，三次计数必须重新开始。

G4 的 NetCDF/GRIB 读取库与变量 allowlist 在 DEC-G4-001 解决前不实施；该决策不阻塞 G1～G3。

## 15. 阶段计划与验收门

### Phase G0：重新基线化规格

产物仅为本文。验收：绑定仓库/commit；复用分类有当前代码证据；所有 Climate 项为 GAP；每个
MUST 有 ID 和预定测试；开放决定被冻结或明确其阻塞阶段。

### Phase G1：核心状态基础

范围：`errors.py`、`paths.py`、`models.py`、`repository.py`、`state.py` 和对应单元测试。
不实现领域工具。验收：PATH/SEC、Context、迁移、原子写、锁、恢复、状态机需求全部 PASS。

### Phase G2：离线工作流 MVP

范围：pipeline/tools/registry、7 个工具、sample/local、CSV inspect、plot/report、端到端测试。
不接入 CDS，不修改 QueryEngine。验收：7 工具暴露；离线全链路及非法顺序/路径通过；原测试无回归。

### Phase G3：Eval、恢复与 Agent 包装

范围：Eval、Trace、四个场景、Hook 轨迹、Skill、README 离线演示。验收：真实离线场景、多轮恢复、
Hook 硬断言、Skill loader 和复现文档通过。Day 10（2026-08-28）总验收通过后名称为
**ClimWorkflow Offline Engineering MVP**。

### Phase G4：真实数据与真实模型

范围：CDS/ERA5、格式读取、mock/marked integration tests、真实 Agent baseline。开始前关闭
DEC-G4-001；默认 CI 仍不访问网络。

- **PHASE-001（MUST，G0～G4，PASS/GAP）**：前一阶段全部适用需求达到 PASS 且人工验收后才能进入下一
  阶段；阶段外实现、测试迁移或完成声明均视为验收失败。
  （Day 10：G0～G3 适用需求均有真实 node ID，Climate pytest / Ruff / 四场景 real_offline
  通过。称谓 **ClimWorkflow Offline Engineering MVP**。G4 未开始。）
- **DOC-001（MUST，G3，PASS）**：README 必须从空 workspace 给出可复制的离线 demo、预期产物、
  恢复步骤和测试命令，不要求密钥。
  （Day 09：`tests/test_climate/test_evals.py::test_readme_offline_demo_from_empty_workspace`；
  `::test_readme_documents_offline_mvp_demo_and_limits`。临时目录按 README 实跑 sample 完成。）

## 16. 需求—测试追踪矩阵

状态说明：G0 只冻结测试设计，不创建测试；BASE-001/002 为 G0 PASS。G1-A（Day 01）已将
PATH-001/002/003、SEC-001（路径/错误脱敏）、ERR-001（共享基础）、ERR-002、SDD-001、TEST-001
更新为 PASS，并回填实际 node ID。G1-B（Day 02）已将 CTX-001/002/003、IO-001（Context/index）、
LOCK-001、CON-001、TEST-002（G1-B 主干）更新为 PASS，并回填实际 node ID。G1-C（Day 03）已将
MIG-001、REC-001/002/003、STATE-001/002/003、IDEM-001、TEST-002（MIG/REC）、TEST-003、
IO-001（事务 marker / 迁移备份）更新为 PASS，并回填实际 node ID。G2-A（Day 04）已将
TOOL-BASE-001（五工具）、TOOL-INIT-001、TOOL-PLAN-001（标准四步）、TOOL-ACQUIRE-001（sample）、
TOOL-ACQUIRE-002、TOOL-INSPECT-001、TOOL-READ-001、PERM-001（分类与 Climate 再校验）、
ERR-001（五工具 envelope）、TEST-004（G2-A 纵切）、SDD-001（G2-A）更新为 PASS/部分 PASS，
并回填实际 node ID。G2-B（Day 05）已将 TOOL-PLAN-001（完整 DAG）、TOOL-ACQUIRE-001（local）、
TOOL-ACQUIRE-002（local 字段互斥）、PATH-004、IDEM-001（G2 工具层）、PERM-001（local 路径再校验）、
TEST-004（local 纵切）、SDD-001（G2-B）、IO-001（local CSV 原子发布）更新为 PASS/部分 PASS，
并回填实际 node ID。G2-B（Day 06）已将 TOOL-PLOT-001、TOOL-REPORT-001、TOOL-BASE-001（七工具）、
REG-001、ERR-001（七工具 envelope）、IO-001（plot/report.md）、IDEM-001（plot/report）、
TEST-004（plot/report 端到端与默认 registry）、SDD-001（G2-B Day 06）、PERM-001（plot path）、
PATH-003（plot/report 仅写 output 区）、SEC-001（report Markdown 脱敏）更新为 PASS，并回填
实际 node ID。Day 07 G2 Gate 已将 ARCH-001、PERM-001（QueryEngine 路径抽取）、CI-001（本机
Climate/Ruff 与依赖钉扎）、PHASE-001（G0～G2）更新为 PASS。Day 07 G3 Foundation 已将
EVAL-001（schema/退出码）、EVAL-003、TEST-005（synthetic/脱敏/退出）更新为 PASS/部分 PASS。
Day 08 已将 EVAL-001（三场景硬断言）、EVAL-002（三核心真实离线）、MEM-001（多轮重启）、
TEST-005（三场景禁网）与 CTX-002（G3 多轮重启）更新为 PASS/部分 PASS。
Day 09 已将 HOOK-001、SKILL-001、DOC-001、EVAL-001/002（Hook）、TEST-005（四场景 + README）、
MEM-001（Skill/compact 指导）、CTX-002（Skill）与 ERR-001（Hook Trace）更新为 PASS。
Day 10（2026-08-28）总验收：G0～G3 适用需求均有真实 pytest node ID；Climate 198 passed；
四场景 `real_offline` `real_pass_rate=1.0`；Ruff PASS。称谓 **ClimWorkflow Offline
Engineering MVP**。G4 需求保持 GAP。
Day 10 追踪矩阵回填已用 `uv run pytest tests/test_climate --collect-only -q`（198 tests）
与 `uv run pytest tests/test_climate/test_evals.py tests/test_skills/test_climate_skill.py --collect-only -q`
（19 + 2）核对实际 node ID。本机 `uv run pytest tests/test_climate -q`（198 passed in 52.29s）。
`test_evals.py` 共 19 项（Foundation 10 + Day 08 六项 + Day 09 Hook/README 三项）。

| 需求 ID | 预定测试 / 评审 | 阶段 | 状态 |
|---|---|---|---|
| BASE-001 | spec review：git HEAD、remote、branch 与页首一致 | G0 | PASS |
| BASE-002 | spec review：搜索旧 PoC 完成声明及 Climate 实现 | G0 | PASS |
| ARCH-001 | git diff：`src/openharness/engine/query.py` 与 `query_engine.py` 无 Climate 改动；`tests/test_climate/test_pipeline.py::test_query_engine_path_rules_block_climate_tools_from_default_registry` 经现有 `_execute_tool_call` 接入 | G1～G3 | PASS |
| PATH-001 | `tests/test_climate/test_paths.py::test_rejects_unsafe_lexical_paths`；`::test_rejects_windows_drive_relative`；`::test_accepts_safe_relative_paths` | G1 | PASS |
| PATH-002 | `tests/test_climate/test_paths.py::test_rejects_link_escape`；`::test_rejects_when_parent_chain_cannot_be_verified` | G1 | PASS |
| PATH-003 | `tests/test_climate/test_paths.py::test_enforces_write_zones`；G2 plot/report 只写 output：`tests/test_climate/test_tools.py::test_plot_png_and_svg_fallback`；`::test_report_dependencies_artifact_and_completion` | G1/G2 | PASS |
| PATH-004 | `tests/test_climate/test_paths.py::test_local_source_must_be_regular_workspace_file`；`tests/test_climate/test_tools.py::test_local_rejects_unsafe_and_non_regular_sources` | G2 | PASS |
| SEC-001 | G1 `tests/test_climate/test_paths.py::test_errors_are_redacted`；G2 `tests/test_climate/test_tools.py::test_report_dependencies_artifact_and_completion`；G3 `tests/test_climate/test_evals.py::test_trace_record_requires_section_12_fields_and_redacts_input`；`::test_sample_pipeline_real_offline_hard_assertions`；`::test_cli_real_offline_runs_core_scenarios`；`::test_pre_tool_output_guard_blocks_before_execute`；`::test_readme_offline_demo_from_empty_workspace` | G1～G4 | PASS |
| SEC-002 | 预定（尚未创建）：`test_cds.py::test_credentials_never_enter_models_or_outputs` + PermissionChecker `.cdsapirc` 全模式拒绝 | G4 | GAP |
| CTX-001 | `tests/test_climate/test_models.py::test_context_v2_invariants_and_roundtrip`；`::test_rejects_unknown_fields`；`::test_rejects_invalid_uuid_and_time_and_enums`；`::test_rejects_duplicate_and_broken_references`；`::test_rejects_non_contiguous_event_sequence`；`::test_version_and_time_invariants`；`::test_rejects_unsafe_artifact_path_and_bad_hash`；`::test_structured_error_shape` | G1 | PASS |
| CTX-002 | G1 PASS：`tests/test_climate/test_repository.py::test_context_is_authoritative_across_new_session`；G3 PASS：`tests/test_climate/test_evals.py::test_multiturn_recovery_destroys_memory_and_restores_from_disk`；Day 09 Skill：`tests/test_skills/test_climate_skill.py::test_climate_skill_frontmatter_and_guidance`（遇错先 `climate_read_context`，禁止 compact/猜测） | G1/G3 | PASS |
| CTX-003 | `tests/test_climate/test_repository.py::test_read_failures_are_distinct_and_non_destructive` | G1 | PASS |
| MIG-001 | `tests/test_climate/test_repository.py::test_v1_migration_is_backed_up_and_idempotent` | G1 | PASS |
| IO-001 | G1 Context/index/事务/迁移备份 PASS：`tests/test_climate/test_repository.py::test_atomic_publish_failure_preserves_stable_files`；`::test_atomic_write_format_and_helper_used`；`::test_v1_migration_is_backed_up_and_idempotent`；`::test_active_run_transaction_recovers_each_fault_point`；G2 sample/local/profile/plot/report 原子发布 PASS：`tests/test_climate/test_tools.py::test_sample_is_deterministic_and_atomic`；`::test_sample_and_local_are_deterministic_and_atomic`；`::test_inspect_is_bounded_and_does_not_touch_dataset`；`::test_plot_png_and_svg_fallback`；`::test_report_dependencies_artifact_and_completion` | G1～G4 | PASS (G1 Context/index/WAL/备份；G2 sample/local CSV/inspect profile/plot/report.md)；GAP (G4 下载) |
| LOCK-001 | `tests/test_climate/test_repository.py::test_concurrent_updates_follow_lock_order`；`::test_active_run_acquires_workspace_before_run_lock`；`::test_lock_unavailable_maps_to_stable_error` | G1 | PASS |
| CON-001 | `tests/test_climate/test_repository.py::test_expected_version_conflict_does_not_write` | G1 | PASS |
| REC-001 | `tests/test_climate/test_repository.py::test_corrupt_or_unwritable_context_is_not_overwritten` | G1 | PASS |
| REC-002 | `tests/test_climate/test_repository.py::test_active_run_transaction_recovers_each_fault_point`（参数：`before_marker`/`marker_only`/`context_written`/`index_written`/`marker_delete_failed`） | G1 | PASS |
| REC-003 | `tests/test_climate/test_repository.py::test_orphan_requires_explicit_resume` | G1 | PASS |
| STATE-001 | `tests/test_climate/test_state.py::test_transition_table`；`::test_transition_table_legal_run`；`::test_transition_table_illegal_run`；`::test_transition_table_legal_step`；`::test_transition_table_illegal_step` | G1 | PASS |
| STATE-002 | `tests/test_climate/test_state.py::test_attempt_and_event_sequence_rules` | G1 | PASS |
| STATE-003 | `tests/test_climate/test_state.py::test_error_recording_preserves_original_failure` | G1 | PASS |
| IDEM-001 | G1 PASS：`tests/test_climate/test_state.py::test_replay_same_input_and_conflict_on_different_input`；G2 PASS：`tests/test_climate/test_tools.py::test_local_dependency_and_idempotency`；`::test_plot_idempotency_and_conflict`；`::test_report_dependencies_artifact_and_completion`；G3 Eval：`tests/test_climate/test_evals.py::test_cached_inspect_real_offline_hard_assertions`（二次 inspect 同输入、version 不变） | G1/G2/G3 | PASS |
| ERR-001 | G1 PASS：`tests/test_climate/test_errors.py::test_error_envelope`；G2 七工具 PASS：`tests/test_climate/test_tools.py::test_all_tool_results_match_error_envelope`；G3 Hook Trace PASS：`tests/test_climate/test_evals.py::test_pre_tool_output_guard_blocks_before_execute`（`CLIMATE_HOOK_BLOCKED`，非 `CLIMATE_INVALID_INPUT`） | G1～G3 | PASS |
| ERR-002 | `tests/test_climate/test_errors.py::test_error_details_allowlist_and_redaction` | G1 | PASS |
| TOOL-BASE-001 | `tests/test_climate/test_tools.py::test_all_tools_use_shared_contracts`；`tests/test_climate/test_registry.py::test_climate_registry_names_unique_and_schema_exportable`；`::test_independent_registry_does_not_overwrite_same_name`；`::test_default_registry_has_exact_climate_tools` | G2 | PASS |
| REG-001 | `tests/test_climate/test_registry.py::test_climate_tool_names_do_not_collide_with_default_registry`；`::test_default_registry_has_exact_climate_tools`；`::test_climate_registry_names_unique_and_schema_exportable`；`::test_independent_registry_does_not_overwrite_same_name` | G2 | PASS |
| TOOL-INIT-001 | `tests/test_climate/test_tools.py::test_init_create_duplicate_and_resume` | G2 | PASS |
| TOOL-PLAN-001 | `tests/test_climate/test_tools.py::test_plan_validates_dag_and_is_atomic`；`::test_plan_rejects_illegal_dag_without_partial_write`（参数：`missing_action_type`/`duplicate_step_id`/`missing_dependency`/`self_dependency`/`cycle_inspect_plot`/`report_cannot_reach_plot`）；`::test_plan_step_fields_are_strict`；`::test_plan_cannot_replace_after_business_step_started` | G2 | PASS |
| TOOL-ACQUIRE-001 | sample PASS：`tests/test_climate/test_tools.py::test_sample_is_deterministic_and_atomic`；`tests/test_climate/test_pipeline.py::test_offline_vertical_slice_from_empty_workspace`；local PASS：`tests/test_climate/test_tools.py::test_sample_and_local_are_deterministic_and_atomic`；`tests/test_climate/test_pipeline.py::test_offline_local_vertical_slice_from_empty_workspace` | G2 | PASS |
| TOOL-ACQUIRE-002 | `tests/test_climate/test_tools.py::test_acquire_mode_fields_and_no_implicit_fallback`；`tests/test_climate/test_registry.py::test_rejects_extra_fields_and_invalid_uuid_and_mode`；`tests/test_climate/test_pipeline.py::test_illegal_order_and_cds_are_stable_errors` | G2 | PASS |
| TOOL-INSPECT-001 | `tests/test_climate/test_tools.py::test_inspect_is_bounded_and_does_not_touch_dataset`；`tests/test_climate/test_pipeline.py::test_inspect_rejects_unsafe_path` | G2 | PASS |
| TOOL-PLOT-001 | `tests/test_climate/test_tools.py::test_plot_png_and_svg_fallback`；`::test_plot_rejects_columns_paths_and_uninspected_data`；`::test_plot_idempotency_and_conflict`；`tests/test_climate/test_pipeline.py::test_offline_vertical_slice_from_empty_workspace`；`::test_offline_sample_svg_fallback_end_to_end` | G2 | PASS |
| TOOL-REPORT-001 | `tests/test_climate/test_tools.py::test_report_dependencies_artifact_and_completion`；`tests/test_climate/test_pipeline.py::test_offline_vertical_slice_from_empty_workspace`；`::test_offline_local_vertical_slice_from_empty_workspace` | G2 | PASS |
| TOOL-READ-001 | `tests/test_climate/test_tools.py::test_read_context_is_bounded_redacted_and_read_only` | G2 | PASS |
| PERM-001 | G2 PASS：`tests/test_climate/test_tools.py::test_tool_permission_classification_and_path_forwarding`；`::test_local_rejects_unsafe_and_non_regular_sources`；`tests/test_climate/test_registry.py::test_read_only_classification`；`tests/test_climate/test_pipeline.py::test_inspect_rejects_unsafe_path`；`::test_query_engine_path_rules_block_climate_tools_from_default_registry` | G2 | PASS |
| HOOK-001 | `tests/test_climate/test_evals.py::test_pre_tool_output_guard_blocks_before_execute`（execute=0、Context/文件树零变化、`provenance=hook`）；`::test_real_offline_scenarios_and_hook_provenance`；`::test_cli_real_offline_runs_core_scenarios` | G3 | PASS |
| MEM-001 | Day 08：`tests/test_climate/test_evals.py::test_multiturn_recovery_destroys_memory_and_restores_from_disk`。Day 09：`tests/test_skills/test_climate_skill.py::test_climate_skill_frontmatter_and_guidance` | G3 | PASS |
| SKILL-001 | `tests/test_skills/test_climate_skill.py::test_climate_skill_loads_from_project_directory`；`::test_climate_skill_frontmatter_and_guidance` | G3 | PASS |
| EVAL-001 | Foundation：`tests/test_climate/test_evals.py::test_scenario_requires_fields_and_mode_enum`；`::test_load_sample_pipeline_yaml_roundtrip`；`::test_trace_record_requires_section_12_fields_and_redacts_input`；`::test_hard_assertion_success_and_failure`；`::test_cli_nonzero_when_hard_assertion_fails`；`::test_cli_accepts_suite_and_mode_flags`；`::test_missing_suite_or_scenario_returns_stable_diagnostic`。Day 08：`::test_sample_pipeline_real_offline_hard_assertions`；`::test_cached_inspect_real_offline_hard_assertions`；`::test_multiturn_recovery_destroys_memory_and_restores_from_disk`；`::test_cli_real_offline_runs_core_scenarios`。Day 09 Hook：`::test_pre_tool_output_guard_blocks_before_execute`；`::test_real_offline_scenarios_and_hook_provenance` | G3 | PASS |
| EVAL-002 | Day 08：`tests/test_climate/test_evals.py::test_sample_pipeline_real_offline_hard_assertions`；`::test_cached_inspect_real_offline_hard_assertions`；`::test_multiturn_recovery_destroys_memory_and_restores_from_disk`；`::test_real_offline_scenarios_and_hook_provenance`；`::test_real_offline_forbids_network`；`::test_cli_real_offline_runs_core_scenarios`。Day 09：`::test_pre_tool_output_guard_blocks_before_execute` | G3 | PASS |
| EVAL-003 | `tests/test_climate/test_evals.py::test_synthetic_dry_run_is_labeled_and_excluded_from_real_pass_rate`；`::test_runner_synthetic_adapter_does_not_call_tools`；`::test_real_agent_is_schema_recognized_but_g3_refuses_execution` | G3 | PASS |
| SDD-001 | G1-A/B/C、G2-A/B Day 04～06、Day 07 Eval Foundation、Day 08 real_offline、Day 09 Hook/Skill/README：RED→GREEN；Day 09 node ID：`::test_pre_tool_output_guard_blocks_before_execute`；`tests/test_skills/test_climate_skill.py::test_climate_skill_loads_from_project_directory`；`::test_climate_skill_frontmatter_and_guidance`；`::test_readme_offline_demo_from_empty_workspace`；`::test_readme_documents_offline_mvp_demo_and_limits` | G1～G4 | PASS |
| TEST-001 | G1 PASS：`tests/test_climate/test_paths.py` 的 `::test_accepts_safe_relative_paths`；`::test_rejects_unsafe_lexical_paths`；`::test_rejects_link_escape`；`::test_rejects_when_parent_chain_cannot_be_verified`；`::test_enforces_write_zones`；`::test_errors_are_redacted`；`::test_rejects_windows_drive_relative`；G2 PATH-004 的 `::test_local_source_must_be_regular_workspace_file` 计入 PATH-004/TEST-004 | G1 | PASS |
| TEST-002 | `tests/test_climate/test_repository.py` 全文件（含 G1-B 主干与 `::test_v1_migration_is_backed_up_and_idempotent`；`::test_corrupt_or_unwritable_context_is_not_overwritten`；`::test_active_run_transaction_recovers_each_fault_point`；`::test_orphan_requires_explicit_resume`；`::test_active_run_acquires_workspace_before_run_lock`） | G1 | PASS |
| TEST-003 | `tests/test_climate/test_state.py` 全文件（含 `::test_transition_table`；`::test_attempt_and_event_sequence_rules`；`::test_error_recording_preserves_original_failure`；`::test_replay_same_input_and_conflict_on_different_input` 及合法/非法参数化表） | G1 | PASS |
| TEST-004 | G2 PASS：`tests/test_climate/test_registry.py` 全文件（含 `::test_climate_registry_names_unique_and_schema_exportable`；`::test_climate_tool_names_do_not_collide_with_default_registry`；`::test_default_registry_has_exact_climate_tools`）；`tests/test_climate/test_tools.py` 全文件（含 `::test_plot_png_and_svg_fallback`；`::test_plot_rejects_columns_paths_and_uninspected_data`；`::test_plot_idempotency_and_conflict`；`::test_report_dependencies_artifact_and_completion`）；`tests/test_climate/test_pipeline.py`（`::test_offline_vertical_slice_from_empty_workspace`；`::test_offline_local_vertical_slice_from_empty_workspace`；`::test_offline_sample_svg_fallback_end_to_end`；`::test_illegal_order_and_cds_are_stable_errors`；`::test_inspect_rejects_unsafe_path`；`::test_query_engine_path_rules_block_climate_tools_from_default_registry`）；`tests/test_climate/test_paths.py::test_local_source_must_be_regular_workspace_file` | G2 | PASS |
| TEST-005 | Foundation：`tests/test_climate/test_evals.py::test_scenario_requires_fields_and_mode_enum`；`::test_load_sample_pipeline_yaml_roundtrip`；`::test_trace_record_requires_section_12_fields_and_redacts_input`；`::test_hard_assertion_success_and_failure`；`::test_cli_nonzero_when_hard_assertion_fails`；`::test_synthetic_dry_run_is_labeled_and_excluded_from_real_pass_rate`；`::test_cli_accepts_suite_and_mode_flags`；`::test_real_agent_is_schema_recognized_but_g3_refuses_execution`；`::test_missing_suite_or_scenario_returns_stable_diagnostic`；`::test_runner_synthetic_adapter_does_not_call_tools`。Day 08：`::test_sample_pipeline_real_offline_hard_assertions`；`::test_cached_inspect_real_offline_hard_assertions`；`::test_multiturn_recovery_destroys_memory_and_restores_from_disk`；`::test_real_offline_scenarios_and_hook_provenance`；`::test_real_offline_forbids_network`；`::test_cli_real_offline_runs_core_scenarios`。Day 09：`::test_pre_tool_output_guard_blocks_before_execute`；`::test_readme_offline_demo_from_empty_workspace`；`::test_readme_documents_offline_mvp_demo_and_limits` | G3 | PASS |
| TEST-006 | 预定（尚未创建）：`test_cds.py` mock + marker 注册/默认 deselection 检查 | G4 | GAP |
| CI-001 | Day 10：`uv run pytest tests/test_climate --collect-only -q`（198 tests）；本机 `uv run pytest tests/test_climate -q`（198 passed in 52.29s）；`uv run ruff check src tests scripts evals` PASS；`uv run python -m evals --suite climate --mode real_offline` 4/4、`real_pass_rate=1.0`（墙钟 10850ms）。本机 `uv run pytest -q`：1325 passed, 23 failed, 11 skipped（失败均为 OpenHarness Windows POSIX/时区/符号链接/cmd，0 个 Climate）。GitHub 3.10/3.11 未推送 | G1～G4 | PASS (本机 Climate/Ruff/real_offline)；GAP (未推送的 GitHub Actions) |
| CDS-001 | 预定（尚未创建）：`test_cds.py::test_cds_request_validation_and_optional_dependency` | G4 | GAP |
| CDS-002 | 预定（尚未创建）：`test_cds.py::test_download_publish_validates_content_and_cleans_part` | G4 | GAP |
| CDS-003 | 预定（尚未创建）：`test_cds.py::test_retry_policy_only_timeout_and_rate_limit` | G4 | GAP |
| CDS-004 | 预定（尚未创建）：`test_cds.py::test_fallback_is_explicit_and_audited` | G4 | GAP |
| MODEL-001 | 预定（尚未创建）：`evals/baselines/climate-real-<commit>.json` 三次运行硬断言 | G4 | GAP |
| PHASE-001 | Day 10：G0～G3 适用需求 PASS 且有真实 node ID；Climate pytest / Ruff / 四场景 real_offline 通过。称谓 ClimWorkflow Offline Engineering MVP。G4 未开始 | G0～G4 | PASS (G0～G3)；GAP (G4) |
| DOC-001 | `tests/test_climate/test_evals.py::test_readme_offline_demo_from_empty_workspace`；`::test_readme_documents_offline_mvp_demo_and_limits` | G3 | PASS |

## 17. Definition of Done

一个阶段仅在以下条件全部满足时完成：

1. 该阶段所有适用需求从 GAP 更新为 PASS，且追踪矩阵填写实际测试 node ID；
2. 测试遵循 SDD，阶段测试、必要回归、ruff 和 CI 通过；
3. 没有阶段外修改、旧 Climate 代码迁移、凭证、缓存或 Eval 临时产物；
4. 所有持久化变更经过安全路径、锁、版本检查和原子发布；
5. 失败路径有稳定错误码并通过脱敏检查；
6. 文档、工具 schema、Context schema、测试和实现一致；
7. 开放决策不阻塞当前或下一阶段；
8. 人工验收确认后才允许单独创建提交；提交和推送不属于阶段自动动作。

离线 MVP（G3）额外要求：

```powershell
uv run pytest tests/test_climate -q
uv run pytest -q
uv run ruff check src tests scripts evals
uv run python -m evals --suite climate --mode real_offline
```

G4 额外要求 mock 测试通过、默认 CI 无网络、marked integration 明确选择后可运行，以及
MODEL-001 baseline 达标。

## 18. 已冻结决策与待决问题

### 已冻结

- DEC-001：业务 Context 使用 workspace 内 `.climate/`，不复用 Memory 文件。
- DEC-002：run Context schema 从 v2 开始，并以 fixture 固化 v1→v2 迁移。
- DEC-003：7 工具接入默认 ToolRegistry，不建立 Climate 专用 QueryEngine。
- DEC-004：所有用户文件路径限 workspace 内；G0～G4 均不支持外部绝对路径。
- DEC-005：plot 在 matplotlib 缺失时输出真实 SVG，离线 MVP 不因该可选依赖失效。
- DEC-006：Hook 输出路径 guard 使用 PRE_TOOL_USE；POST_TOOL_USE 仅观测，不承担回滚。
- DEC-007：权威恢复只读 Context；Memory/compact 只提供导航提示。
- DEC-008：锁沿用上游阻塞语义，v0.1 不增加锁超时 API。
- DEC-009：沿用 `QueryEngine` 每次用户输入默认 `max_turns=8`；标准离线链路最多使用 7 个模型
  turn（6 个顺序工具轮次加最终回复），恢复发生在新的用户输入中，不提高默认值。

### 待决且明确阻塞

- **DEC-G4-001（阻塞 G4，不阻塞 G1～G3）**：在开始 G4 前，经最小技术 spike 冻结 NetCDF/GRIB
  读取依赖、magic/content 校验方法、ERA5 dataset/variable allowlist 和 CI 安装策略。未决期间
  不得实现或声称完成 CDS/NetCDF/GRIB 能力。

当前没有阻塞 G1 的开放决策。
