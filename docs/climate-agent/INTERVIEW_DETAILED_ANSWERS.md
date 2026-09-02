# ClimWorkflow / OpenHarness 二次开发：面试详细答案

## 0. 使用前提

本文用于准备 AI Agent 平台、Agent 应用工程和大模型应用开发岗位面试。

截至 2026-09-01 Day 15 本机验收：G0～G3 为 **ClimWorkflow Offline Engineering MVP**；
G4 本机 PASS（`climate_integration` 1 passed；`real_agent` baseline 3/3）。GitHub Actions
未推送。因此面试必须区分：

- **OpenHarness 已有能力**：可以用现在的源码解释实现原理，不能说成自己写的 Runtime。
- **ClimWorkflow 已验证能力**：G1～G4 适用需求均有 pytest node ID；数字以 SPEC / README
  Day 15 实测表为准。
- **仍为 GAP**：未推送的 GitHub Actions；Windows 上游环境失败不计入 Climate。

不得把 OpenHarness 上游已有代码描述成自己的实现。完成项目后，准确表述应是：

> 我基于 OpenHarness 的 QueryEngine、Tool、Permission、Hook、Compact 和 Skill 扩展点，
> 新增了 Climate 领域工具、持久化 Context Repository、状态机、恢复机制和 Eval，而没有重写
> Agent Runtime。

### 事实核对入口

- Agent Loop：`src/openharness/engine/query.py::run_query`
- Engine 门面：`src/openharness/engine/query_engine.py::QueryEngine`
- Tool 抽象：`src/openharness/tools/base.py`
- 默认工具注册：`src/openharness/tools/__init__.py::create_default_tool_registry`
- 权限：`src/openharness/permissions/checker.py::PermissionChecker`
- Hook：`src/openharness/hooks/executor.py::HookExecutor`
- 会话压缩：`src/openharness/services/compact/__init__.py`
- Session Memory：`src/openharness/services/session_memory/__init__.py`
- Skill 加载：`src/openharness/skills/loader.py::load_skill_registry`
- Climate 设计契约：`docs/climate-agent/SPEC.md`

---

## 1. 面试官最关心什么，以及本项目应该怎么回答

### 1.1 Agent 平台 / 框架研发岗

面试官通常优先考察 Agent Runtime，而不是气象知识。回答主线应是：

1. OpenHarness 如何把模型输出转成 Tool 调用。
2. Tool schema、参数校验、权限、Hook 和执行结果如何形成受控边界。
3. ClimWorkflow 如何在该边界内增加持久化业务状态，而不侵入 QueryEngine。
4. 长任务如何通过状态机、原子写、锁、WAL 和幂等实现恢复。
5. 如何用 Trace 和硬断言证明 Agent 真的按预期运行。

本项目最有区分度的不是“调用了气象 API”，而是：

- 把聊天上下文与权威业务状态分离；
- 把模型的非确定性决策限制在确定性的工具和状态机边界内；
- 把成功 Demo 变成可复现、可失败、可审计的 Eval。

### 1.2 Agent 应用研发岗

除了通用 Agent 能力，还要回答“为什么这个业务值得用 Agent”：

- 用户输入可能是自然语言目标，不一定给出完整数据源、变量和输出形式；
- Agent 负责理解目标、选择工具和组织多轮交互；
- 工具内部的数据检查、路径安全、状态转换和文件写入保持确定性；
- 对固定且无歧义的任务，普通 Pipeline 更合适，不应为了使用 LLM 强行 Agent 化。

### 1.3 算法 / 模型岗

当前项目的核心是 Agent 工程，不是模型训练。它不能证明：

- SFT、DPO、PPO、GRPO 等后训练能力；
- RAG 召回和重排优化；
- 推理引擎或训练系统优化；
- Agentic RL 或 Multi-Agent 算法研究。

若投递纯算法岗，应补充模型、RAG 或训练项目；不能靠本项目覆盖所有岗位要求。

### 1.4 气象领域在面试中的作用

气象领域不是可有可无的外壳，它提供了真实约束：

- CSV、NetCDF、GRIB 等多格式和科学数据校验；
- CDS 外部服务的超时、限流、认证和错误内容；
- 大文件、部分下载、单位、经纬度、时间范围；
- “静默 fallback 会生成错误结论”的高风险场景。

但面试回答不应变成气象知识展示。正确关系是：

> 气象场景提供约束和失败模式，通用 Agent 架构负责安全、恢复、编排和评测。

### 1.5 当前项目的优势与短板

优势：

- 基于真实 Agent Runtime 扩展，不是单文件 Prompt Demo；
- 强调 Durable Execution、错误模型和安全边界；
- Eval 检查工具序列、状态、artifact 和 Hook provenance；
- 有清晰的复用矩阵，能解释个人贡献。

短板：

- 当前尚未开发，不能作为已完成经历投递；
- G3 前没有真实模型 baseline；
- 没有 RAG、Multi-Agent、线上服务、高并发或部署；
- OpenHarness 默认模式并非全局 workspace 硬沙箱，PermissionChecker 主要是策略层；
- G4 科学数据依赖和 allowlist 仍需技术 spike 冻结。

---

## 2. 项目与个人贡献

### Q1：OpenHarness 是你开发的吗？你具体实现了什么？

**答案：**

不是。OpenHarness 是已有 Agent Runtime，我做的是基于其扩展点进行二次开发。

OpenHarness 已提供：

- `QueryEngine` 和 `run_query` 工具感知循环；
- `BaseTool`、`ToolRegistry`、Pydantic schema 和 `ToolResult`；
- `PermissionChecker` 的 default、plan、full_auto 权限模式；
- PRE/POST Tool Hook、会话压缩、Session Memory 和项目 Skill loader。

ClimWorkflow 的个人实现范围应在完成后表述为：

- 7 个 Climate Tool；
- 版本化 WorkspaceIndex / RunContext；
- Context Repository、状态机、幂等和 active-run WAL 恢复；
- Climate 路径安全、统一错误 envelope 和脱敏；
- 真实离线 Eval、Hook 阻断场景及 CDS 可靠下载。

核心原则是复用通用 Runtime，不修改 QueryEngine 执行语义。

### Q2：哪些模块是复用上游的，哪些是新增或扩展的？

**答案：**

复用：

- `QueryEngine`：模型与工具的循环；
- `BaseTool` / `ToolRegistry`：工具协议和注册；
- `PermissionChecker`：权限模式和敏感路径基础防护；
- `HookExecutor`：生命周期 Hook；
- `atomic_write_text` 和 `exclusive_file_lock`：文件级原子写与跨平台锁；
- compact、Session Memory 和 Skill loader。

扩展：

- 默认 Registry 最终增加 7 个 Climate Tool；
- `SENSITIVE_PATH_PATTERNS` 在 G4 增加 `.cdsapirc`；
- CI 增加 Climate/Eval 测试和 Ruff 范围。

当前 `ToolRegistry.register()` 对同名 key 会直接覆盖，因此接入 7 个工具前必须先测试名称冲突，
不能把“注册成功”误当成“不会覆盖上游工具”。

新增：

- `src/openharness/climate/` 领域实现；
- `.climate/` Context 与 artifact 目录；
- `evals/climate/` 场景、Trace 和 runner；
- `.openharness/skills/climate-ds/SKILL.md`。

### Q3：为什么不直接修改 QueryEngine？

**答案：**

因为 QueryEngine 负责通用执行语义：构造模型请求、解析 tool use、权限检查、执行工具、回填
tool result 和继续模型轮次。Climate 的状态、依赖和恢复属于领域契约。

如果把 Climate 状态机写进 QueryEngine：

- 通用 Runtime 会耦合特定业务；
- 上游升级和回归风险增大；
- 其他 Tool 也会被迫理解 Climate 语义；
- 很难证明二次开发边界。

因此 Context 通过 Repository 和 Tool 内部 mutation 接入，轨迹通过现有 metadata/Hook 接入。

### Q4：这个项目最难的技术问题是什么？

**答案：**

不是画图或调用 CDS，而是保证跨进程长任务的状态一致性。

具体困难包括：

- Context 和 active run index 是两个文件，单次 `os.replace` 不能让二者组成事务；
- 进程可能在 step 标记为 running 后、artifact 发布前崩溃；
- 两个进程可能同时修改同一个 run；
- LLM 可能重复调用或改变已成功 step 的输入；
- 恢复不能依赖聊天记录猜测。

设计使用固定锁顺序、`expected_version`、active-run WAL、状态转换表和输入哈希共同解决。

### Q5：如果去掉 LLM，这个系统还剩下什么价值？

**答案：**

仍然剩下一个可测试的领域工作流内核：

- 结构化工具；
- Context Repository；
- 状态机和依赖验证；
- 幂等、恢复和安全文件访问；
- 离线 Eval 和 artifact 审计。

这恰好说明 LLM 只负责理解目标和选择动作，不负责数据完整性与事务正确性。固定任务甚至可以直接
用确定性 Pipeline 驱动这些工具。

---

## 3. Agent 通用原理

### Q6：OpenHarness 一次 Agent Loop 是怎样执行的？

**答案：**

`QueryEngine.submit_message()` 的主链路是：

1. 清理恢复出的异常消息序列，并追加用户消息；
2. 触发 `USER_PROMPT_SUBMIT` Hook；
3. 构造 `QueryContext`，包含模型、工具 Registry、权限、cwd、Hook 和 max_turns；
4. `run_query()` 在每个模型 turn 前检查是否需要 compact；
5. 通过 `tool_registry.to_api_schema()` 把工具 schema 放入模型请求；
6. 流式接收文本、重试事件和最终 assistant message；
7. 若没有 tool use，触发 STOP Hook 并结束；
8. 若有一个 tool call，顺序执行；若同一响应中有多个 tool call，用 `asyncio.gather` 并发执行；
9. 将每个结果转换成与 `tool_use_id` 对应的 `ToolResultBlock`；
10. 把结果作为 user message 追加，再进入下一模型 turn。

达到 `max_turns` 仍无最终回答时抛出 `MaxTurnsExceeded`。

### Q7：Tool schema 如何交给模型？参数校验在哪一层发生？

**答案：**

每个 Tool 继承 `BaseTool`，提供 `name`、`description`、`input_model` 和 `execute()`。
`BaseTool.to_api_schema()` 调用 Pydantic 的 `model_json_schema()`，生成：

```text
name + description + input_schema
```

Registry 汇总后随每次模型请求发送。模型返回原始字典后，QueryEngine 在执行前调用
`tool.input_model.model_validate(tool_input)`。

需要区分两层校验：

- Pydantic：类型、范围、必填字段和 `extra="forbid"`；
- Tool 业务校验：跨字段互斥、plan 依赖、状态转换、文件内容和幂等冲突。

Climate Tool 必须显式使用严格 Pydantic 配置，不能假设所有上游 Tool 都自动禁止多余字段。

### Q8：ReAct、Plan-and-Execute 和固定 Workflow 有什么区别？

**答案：**

- ReAct：模型每轮根据观察决定下一动作，灵活但路径不稳定。
- Plan-and-Execute：先形成计划，再逐步执行，适合长任务和依赖检查。
- 固定 Workflow：步骤和依赖由代码确定，可预测、易测试，但适应性较弱。

ClimWorkflow 是混合设计：

- Agent 负责将自然语言目标转成结构化 plan 和工具调用；
- Climate 状态机负责验证 DAG、依赖和转换；
- 标准演示固定为 acquire → inspect → plot → report；
- 一般 v0.1 plan 允许 4～32 个 step，但不实现通用 DAG 调度器。

### Q9：为什么 Context 不能只保存在对话历史中？

**答案：**

对话会被 compact、截断、重启或由模型错误概括；ToolResult 也可能因长度被 offload。它不适合作为
事务状态。

ClimWorkflow 把 `.climate/` 下的 WorkspaceIndex 和 RunContext 定义为权威状态，保存：

- run/step 状态；
- version、attempts、输入哈希；
- artifact 相对路径和摘要；
- 连续事件序列；
- 结构化错误。

对话、Memory 和 compact summary 只提供导航信息。恢复时必须先调用
`climate_read_context`，不能从摘要推断成功。

### Q10：Memory、Conversation Context 和业务状态有什么区别？

**答案：**

- Conversation Context：当前发送给模型的消息序列，包含用户、assistant、tool use/result。
- OpenHarness Memory：Session Memory、compact summary、可选 durable memory，用于跨长对话保留
  目标、最近工作和导航信息。
- Climate 业务状态：WorkspaceIndex / RunContext，是决定 step 是否成功、artifact 是否有效的
  唯一权威来源。

Session Memory 当前以 Markdown 原子写入数据目录，内容包括 goal、next step、verified work、
active artifacts 和最近消息摘要，但它不具备 Climate 的 schema、状态机和事务约束。

### Q11：如何防止模型跳过 plan，直接调用 report？

**答案：**

不能只依赖 Prompt。每个 mutating Tool 都在执行前检查：

- run 是否存在；
- step 是否在持久化 plan 中；
- action 是否匹配 Tool；
- depends_on 是否全部 succeeded；
- 当前状态转换是否合法；
- 输入是否与已成功 step 的幂等键一致。

因此模型可以发出错误调用，但工具会返回
`CLIMATE_DEPENDENCY_NOT_READY` 或 `CLIMATE_INVALID_TRANSITION`，Context 不发生变化。

### Q12：`max_turns` 用尽后如何恢复？

**答案：**

OpenHarness 的 `QueryEngine` 构造器默认是 8 turns，但完整应用 Runtime 可通过 Settings 覆盖，
当前 Settings 默认值是 200。面试时不能笼统声称所有入口固定为 8。

ClimWorkflow Eval 应固定实际配置。标准离线链设计为最多 7 个模型 turn：6 个顺序工具轮次加最终
回复。若仍达到上限：

- 已持久化的 Context 不丢失；
- 新用户输入/新会话先调用 `climate_read_context`；
- 根据权威 step 状态继续；
- 不通过无限增大 max_turns 掩盖规划问题。

OpenHarness 还提供 `continue_pending()` 继续工具结果后的模型轮次，但 Climate 跨会话业务恢复仍以
Context 为准。

### Q13：Tool 调用失败后由谁决定重试？

**答案：**

需要区分三种重试：

- 模型 API 的瞬时失败：API client 通过 `ApiRetryEvent` 暴露重试状态；
- 普通 Tool 业务失败：QueryEngine 不自动重放，结果返回模型，由模型或用户决定下一步；
- CDS timeout/rate-limit：Climate Tool 内实施最多 3 次的有界指数退避。

认证、输入、格式、路径和永久外部错误不重试。失败 step 是否允许 retry 还必须由状态机和
`retryable` 字段共同约束。CDS 的多次传输重试发生在一次 Tool/step attempt 内，不应重复增加
step `attempts`；只有重新进入 step `running` 才增加 attempts。

### Q14：为什么当前项目不需要 Multi-Agent？

**答案：**

Climate v0.1 是依赖明确、共享状态强的单工作流。引入多个 Agent 会增加：

- 状态所有权和消息一致性问题；
- 重复工具调用和成本；
- 评测维度；
- 故障恢复复杂度。

OpenHarness 已有 AgentTool、任务和协调能力，但项目不应为了关键词使用 Multi-Agent。只有当不同
角色拥有独立目标、上下文和并行收益，例如“数据检索—科学验证—报告审校”，且 Eval 证明收益后，
才值得引入。

---

## 4. 持久化与状态机

### Q15：为什么要同时使用文件锁和 `expected_version`？

**答案：**

两者解决不同问题：

- 文件锁把一次进程内 read-modify-write 临界区串行化；
- `expected_version` 检测调用方依据的旧快照，避免已经过期的业务写入覆盖新状态。

即使获取锁成功，调用方也可能在获取锁前持有旧 version。因此在锁内重新读取并比较 version；
不一致返回 `CLIMATE_VERSION_CONFLICT` 且不写文件。

### Q16：原子写是否等于事务？

**答案：**

不等于。

`atomic_write_text` 使用同目录临时文件、flush、fsync 和 `os.replace`，保证单个文件的读者只能看到
旧版本或新版本，不会看到半截内容。

它不能保证：

- 多文件同时成功；
- 两个写者不会丢失更新；
- 外部下载和 Context 更新构成整体事务。

因此还需要锁、version 和 active-run WAL。

### Q17：进程在写 Context 和更新 active index 之间崩溃怎么办？

**答案：**

创建/切换 active run 前先写 active-run transaction marker，记录：

- old/new active run；
- run Context 是否已写；
- index 是否已写。

恢复时在 workspace lock 下根据文件事实决定：

- 新 Context 有效：补写 index；
- 新 Context 不存在或无效：恢复旧 active pointer；
- index 未引用但存在的有效 run：列为 orphan，只有显式 `resume_run_id` 才能激活。

marker 删除失败不影响已完成事务，后续恢复应幂等清理。

### Q18：为什么残留的 `running` step 不能直接判定为成功？

**答案：**

`running` 只表示“执行意图已持久化”，不证明外部副作用完成。进程可能在：

- 文件只写到 `.part`；
- CDS 请求已发出但响应未发布；
- artifact 已生成但 Context 未登记；
- Context 已登记但调用结果未返回。

恢复时把残留 running 转为 failed，错误码 `CLIMATE_INTERRUPTED`，清理该 step 的 `.part`，由显式
retry 再执行。自动猜成功会产生不可审计状态。

### Q19：如何实现同输入幂等重放？

**答案：**

Tool 先把业务输入规范化，再计算 SHA-256，保存为 step 的 `input_hash`。

- step 已 succeeded 且 hash 相同：返回持久化结果，不增加 version、attempts 或事件；
- step 已 succeeded 但 hash 不同：返回 `CLIMATE_IDEMPOTENCY_CONFLICT`；
- failed 且错误可恢复：允许进入 running，attempts 加一。

不能只用 step_id 作为幂等键，因为同一 step_id 可能被不同参数重放。

### Q20：如何处理两个进程同时更新同一个 run？

**答案：**

使用固定锁顺序避免死锁：

1. 需要 workspace/index 时先获取 workspace lock；
2. 再按规范 run_id 顺序获取 run lock；
3. 锁内重新读取文件；
4. 校验 `expected_version`；
5. 完成 mutation 和原子写。

第二个写者若基于旧 version，会得到版本冲突并重新读取，而不是覆盖第一个写者。

### Q21：WAL 恢复为什么不能由只读工具偷偷执行？

**答案：**

因为权限系统依据 `is_read_only()` 决定 plan/default 模式是否允许执行。若
`climate_read_context` 声称只读却完成 WAL、迁移或删除 marker，就绕过了用户对 mutation 的授权。

因此 SPEC 规定 read_context 文件系统纯只读：

- v1 返回 `CLIMATE_SCHEMA_UNSUPPORTED`；
- 检测到未完成 WAL 返回 `CLIMATE_RECOVERY_REQUIRED`；
- 由受权限控制的 mutating Tool 或显式 Repository API 执行恢复。

### Q22：如何证明恢复后不会出现两个 active run？

**答案：**

不能只靠代码审阅，需要故障注入测试：

- 在 marker 创建、Context 写入、index 写入和 marker 删除等每个点模拟崩溃；
- 对每个快照重复执行 recovery；
- 断言 index 最多一个 `active_run_id`；
- 断言重复恢复不增加 version/事件；
- 断言 orphan 不会被自动选为“最新 run”；
- 断言损坏 Context 原字节不变。

---

## 5. 工具、安全与 Hook

### Q23：为什么 Pydantic 校验后还需要业务语义校验？

**答案：**

Pydantic 擅长局部结构：

- 字段类型；
- 长度和数值范围；
- enum；
- 多余字段拒绝。

它不能单独判断：

- `mode=local` 时 path 必填，其他模式 path 禁止；
- step 是否属于当前 run 的 plan；
- DAG 是否有环；
- report 的依赖是否已成功；
- artifact 摘要是否与文件一致。

这些需要 Repository、状态机和领域验证器。

### Q24：PermissionChecker 和 Climate 路径解析器为什么要双重检查？

**答案：**

`PermissionChecker` 负责通用用户授权：

- 敏感路径硬拒绝；
- allowed/denied tool；
- path deny rule 和 command deny；
- plan/default/full_auto 模式。

Climate resolver 负责领域不变量：

- 只允许 workspace 相对路径；
- 禁止 drive-relative、UNC、混合分隔符绕过；
- 检查 symlink/junction realpath 逃逸；
- 写入只能落在固定 `.climate/` zone；
- local 源必须是普通 CSV 文件。

权限允许不等于业务路径安全，所以需要纵深防御。

还要诚实说明上游边界：PermissionChecker 使用 resolve 后路径进行 fnmatch 策略匹配，不是完整的
路径遍历防护；当前 `path_rules` 的 `allow=true` 不形成有效白名单。Docker sandbox 开启时，部分
文件工具才会额外执行 cwd 边界校验。因此 Climate resolver 必须在所有模式下自行强制 workspace
边界，不能把 PermissionChecker 当作安全路径解析器。

### Q25：Windows drive-relative、UNC、junction 有什么风险？

**答案：**

- `C:foo` 不是普通相对路径，它依赖 C 盘当前目录；
- `\\server\share` 或 `\\?\` 可访问 UNC/设备命名空间；
- `/` 与 `\` 混合可能绕过只检查一种分隔符的逻辑；
- junction/symlink 的词法路径在 workspace 内，resolve 后可能逃到外部；
- `CON`、`NUL`、`COM1` 是 Windows 保留设备名。

因此先做跨平台词法拒绝，再做 `resolve()` 后的包含关系检查，不能只用字符串前缀。

### Q26：为什么 local 文件必须复制到 run 目录？

**答案：**

如果 Context 直接引用用户源文件：

- 用户后续修改会让历史结果不可复现；
- 文件可能被删除；
- 同一 run 的摘要和内容会漂移；
- artifact 生命周期不受系统控制。

复制到 run data 目录并计算 size/SHA-256 后，Context 才能把它当作稳定 artifact。源文件保持只读，
目标通过 `.part` 和原子替换发布。

### Q27：Hook 在参数校验前还是之后执行？这有什么影响？

**答案：**

当前 `_execute_tool_call()` 顺序是：

1. `PRE_TOOL_USE`；
2. Registry 查找；
3. Pydantic 校验；
4. 权限检查；
5. `tool.execute()`；
6. 结果 offload/carryover；
7. `POST_TOOL_USE`。

因此 PRE Hook 看到的是原始输入，可以在 schema 或权限检查前阻断；它也不能假设输入已经合法。
POST Hook 发生在副作用之后，只适合观测，不能承担回滚。

### Q28：如何证明 Hook 阻断后工具没有产生副作用？

**答案：**

`pre_tool_output_guard` 场景使用 schema 合法、summary 含固定测试标记的 write_report 输入，并设置
精确 matcher。

硬证据包括：

- spy 断言 `execute()` 调用次数为 0；
- Context version 和 events 前后相同；
- workspace 文件树和摘要前后相同；
- Trace 记录 PRE_TOOL_USE、blocked 和规范 reason code；
- 报告中不存在测试标记。

不能使用本来会被 Pydantic 拒绝的输入冒充 Hook 成功。

### Q29：如何保证 Trace、错误和 Context 不泄露凭证？

**答案：**

采用 allowlist 而不是“事后全字符串替换”：

- error details 只允许稳定、非敏感字段；
- Context 只保存 workspace 相对路径；
- Trace 保存 `input_redacted`，不保存完整原始数据和 traceback；
- 不接受 API key、token 或 `.cdsapirc` 内容作为 Climate 输入；
- CDS 凭证只由 cdsapi 标准外部配置读取；
- PermissionChecker 在 G4 增加 `.cdsapirc` 全模式硬拒绝；
- 测试扫描 home、workspace 绝对路径和已知 secret marker。

---

## 6. Eval 与模型效果

### Q30：Agent 测试为什么不能只断言最终报告存在？

**答案：**

报告存在可能来自：

- 旧缓存；
- mock/伪造成功；
- 跳过 inspect；
- 错误数据 fallback；
- 工具失败后仍写报告；
- Hook 实际未执行。

因此 Eval 还要断言工具序列、错误码、最终状态、Context version、artifact 路径/摘要、Hook 事件和
执行模式。

### Q31：Synthetic dry-run 和 real offline Eval 有什么区别？

**答案：**

Synthetic dry-run 只验证：

- scenario 能否解析；
- assertion wiring；
- Trace/报告格式；
- CLI 失败退出码。

它不执行真实 Climate Tool，不能计入真实通过率。

Real offline 必须通过 Registry、Pydantic、ToolExecutionContext 和真实 Tool 执行 sample/local
流程，但禁止网络和真实模型。两者都不等于 G4 的 `real_agent`。

### Q32：如何判断工具调用序列是否正确？

**答案：**

Scenario 冻结 `expected_tool_sequence`，Trace 为每次调用记录 sequence、name、脱敏输入、错误码和
耗时。硬断言比较：

- 是否缺少/多出工具；
- 顺序是否满足依赖；
- 恢复场景新会话第一个业务动作是否为 read_context；
- Hook 场景是否在 execute 前停止；
- 最终 Context 状态与序列是否一致。

对于同一 assistant response 的并发 tool calls，还需要区分“模型声明顺序”和“实际完成顺序”，
不能用完成时间伪造依赖顺序。

### Q33：为什么需要硬断言和非零退出码？

**答案：**

如果 runner 永远返回 0，CI 无法区分“生成了报告”和“行为正确”。硬断言失败非零使 Eval 能成为
质量门禁，而不是展示页面。

主观质量可附加 Judge，但以下条件必须确定性检查：

- 文件和摘要；
- 状态与 version；
- 工具序列；
- 错误码；
- 禁网；
- 凭证和绝对路径泄露。

### Q34：模型有随机性，为什么 3 次中至少 2 次通过？

**答案：**

这是 G4 smoke baseline 的工程验收阈值，不是统计显著性证明。

它用于避免：

- 单次幸运成功就宣称稳定；
- 一次外部瞬时失败否定整个配置。

三次必须固定 commit、provider、model、effort、max_turns 和 scenario，并使用独立 workspace。
如果需要发布级可靠性，应增加样本量、置信区间、失败分层和长期回归。

### Q35：模型更换后 Baseline 是否还能使用？

**答案：**

不能直接沿用。以下任一变化都应使 baseline 失效并重新运行：

- model/provider/profile；
- Prompt/Skill；
- tool schema；
- scenario/assertion；
- 代码 commit；
- max_turns/effort 等配置。

旧 baseline 可以作为历史对照，但不能代表新配置通过。

### Q36：LLM-as-Judge 有什么问题？哪些条件必须用确定性断言？

**答案：**

LLM Judge 可能有：

- 模型偏好和自洽偏差；
- Prompt 敏感；
- 非确定性；
- 被待评文本注入；
- 成本和版本漂移。

它适合评估报告可读性、解释完整性等主观指标。文件存在、哈希、数值范围、工具序列、状态转换、
敏感信息和错误码必须使用确定性断言。

### Q37：如何定位失败来自模型、工具、状态机还是外部服务？

**答案：**

按层定位：

1. 模型层：是否生成目标 Tool、输入是否符合 schema；
2. Runtime 层：Hook、Registry、Pydantic、Permission 哪一层拒绝；
3. Tool 层：返回哪个稳定错误码；
4. Repository 层：version、锁、原子写、状态转换是否失败；
5. 外部层：timeout、rate-limit、认证、内容无效；
6. Eval 层：哪个 assertion 与证据不一致。

Trace 需要同时保留 tool、hook、Context 和 artifact provenance，不能只保存最终聊天文本。

---

## 7. 气象领域问题

### Q38：ERA5/CDS 数据下载为什么需要 `.part` 文件？

**答案：**

直接写最终文件名时，其他读者可能把部分下载当成完整数据。正确流程是：

1. 在目标同目录写唯一 `.part`；
2. 下载完成后 flush/fsync；
3. 验证非空、magic/content、扩展名和科学格式；
4. 计算摘要；
5. `os.replace` 发布最终文件；
6. 失败时清理 `.part`，不注册 artifact。

### Q39：如何验证下载到的文件不是 HTML 错误页面？

**答案：**

不能只检查 HTTP 成功或扩展名。至少检查：

- 文件非空和合理最小尺寸；
- 响应/文件头不是 HTML、JSON 错误正文；
- NetCDF/GRIB 的 magic/content；
- 使用冻结的解析库真正打开 fixture；
- 扩展名、media type 和实际格式一致。

具体 NetCDF/GRIB 库和 magic 策略需在 G4 技术 spike 后冻结，当前不能声称已实现。

### Q40：NetCDF、GRIB 和 CSV 有什么差别？

**答案：**

- CSV：二维文本表，易调试，但缺少原生多维坐标、变量属性和压缩。
- NetCDF：常用于带维度、坐标、变量属性的科学数组，适合气候数据分析。
- GRIB：气象业务常用的紧凑二进制消息格式，编码和参数表更专业。

G2 只支持 CSV。NetCDF/GRIB 属于 G4，依赖和解析策略必须先通过 DEC-G4-001。

### Q41：经度、纬度、时间、变量单位如何校验？

**答案：**

请求侧：

- area 顺序固定为 north、west、south、east；
- 经纬度有界，且 north > south；
- start ≤ end，最长 366 天；
- dataset 和 variables 使用 allowlist。

数据侧：

- 检查坐标和时间维度存在；
- 检查变量属性、单位和缺失值；
- 明确经度表示是 `[-180,180]` 还是 `[0,360]`；
- 单位转换必须显式记录，不能靠变量名猜测。

后半部分的精确规则要在 G4 spike 后按真实 fixture 冻结。

### Q42：为什么 sample fallback 必须显式开启？

**答案：**

静默 fallback 会让用户以为报告基于 ERA5，实际却是样例数据，属于数据 provenance 错误。

只有 `allow_sample_fallback=true`，且 timeout/rate-limit 已耗尽重试时才能 fallback，并记录：

- requested_mode；
- effective_mode；
- fallback_reason。

认证、输入、依赖、格式、路径和写入错误不能 fallback。

### Q43：如果 CDS 超时、限流或认证失败，分别如何处理？

**答案：**

- timeout：`CLIMATE_EXTERNAL_TIMEOUT`，有限指数退避，最多 3 次；
- rate-limit：`CLIMATE_EXTERNAL_RATE_LIMIT`，有限指数退避，最多 3 次；
- 认证及其他永久错误：`CLIMATE_EXTERNAL_FAILED`，不重试、不 fallback；
- optional 依赖缺失：`CLIMATE_DEPENDENCY_MISSING`。

错误输出必须脱敏，不能返回 token、`.cdsapirc` 内容或完整第三方异常文本。

### Q44：为什么固定分析流程不直接写成普通 DAG Pipeline？

**答案：**

如果输入、数据源、步骤和输出完全固定，普通 DAG Pipeline 更简单、更可靠，应该优先使用。

Agent 的价值在于：

- 从自然语言目标补全结构化参数；
- 在 sample/local/CDS、图类型和列之间做受约束选择；
- 发现缺失信息时与用户交互；
- 根据结构化错误调整下一步；
- 跨会话解释和继续任务。

本项目不是让 LLM 取代确定性 Pipeline，而是让 Agent 负责意图和编排，让 Tool/状态机负责执行
正确性。若最终场景没有不确定决策，就应退化为固定 Pipeline。

---

## 8. 90 秒项目介绍参考

当前 G0 阶段只能使用设计态版本：

> 我正在基于 OpenHarness 做一个气象数据工作流 Agent。OpenHarness 已经提供模型循环、Tool、
> Permission、Hook 和会话压缩，我没有重写 Runtime，而是把重点放在通用 Agent 经常缺失的
> Durable Execution 上。我设计了版本化 Context Repository、run/step 状态机、原子写、跨平台锁、
> 乐观并发和 active-run WAL，让任务在 compact、进程中断或新会话后能够从权威状态恢复。业务层
> 计划通过 7 个结构化 Tool 完成数据获取、检查、绘图和报告，并用真实离线 Eval 验证工具序列、
> Context、artifact 摘要和 Hook 阻断。当前只完成规格基线，还不能声称功能已经实现。

项目完成后，把“正在、设计、计划”替换为“实现”前，必须确认对应需求、测试和 baseline 已 PASS。

