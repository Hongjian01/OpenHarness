# ClimWorkflow / OpenHarness 二次开发：面试背诵版

## 0. 必背边界

截至 2026-09-02：G0～G3 称谓仍是 **ClimWorkflow Offline Engineering MVP**；G4 本机 PASS
（真实 CDS smoke 1 passed；固定配置 `real_agent` 3/3）。fork PR #1 GitHub Actions CI #3
（`52fa338`）已绿，可以说“自己 fork 的 CI 已绿”，不得说“已合入 HKUDS”。下文若仍出现
G0“尚未实现”语气，以本节为准。

当前必须说：

> 我基于 OpenHarness 做二次开发，没有重写 Agent Loop。OpenHarness 提供 QueryEngine、Tool、
> Permission、Hook、Compact 和 Skill；我新增了 7 个 Climate 工具、磁盘 Context、状态机、
> WAL 恢复和 Eval。离线路径不需要密钥；G4 才用外部 CDS/模型凭证，凭证不进仓库。

不得说“我实现了 OpenHarness”。Windows 全量 pytest 仍有上游环境失败，Climate 回归以
`tests/test_climate` 为准。

---

## 1. 面试官最关心什么

### Agent 平台岗

主线：Agent Loop → Tool Calling → Context → Durable Execution → Permission/Hook → Eval。

一句话：

> 气象是验证场景，项目核心是安全、可恢复、可评测的长任务 Agent Runtime 扩展。

### Agent 应用岗

主线：用户问题 → 为什么用 Agent → 工具如何落地业务 → 如何控制模型不确定性。

一句话：

> Agent 负责理解和编排，Tool、状态机和 Repository 负责确定性执行。

### 算法岗

本项目不能证明 SFT、RL、RAG 优化和推理加速，更适合 Agent 平台或 AI 应用工程岗。

### 气象领域

重点不是背气象知识，而是说明真实领域约束如何推动安全、恢复和数据 provenance 设计。

---

## 2. 44 个问题速答

### 1. OpenHarness 是你开发的吗？

不是。OpenHarness 是上游 Runtime；我的贡献边界是 Climate Tool、Context Repository、状态机、
恢复、安全和 Eval。

### 2. 哪些复用，哪些新增？

复用 QueryEngine、BaseTool、Registry、Permission、Hook、原子写、文件锁、Compact 和 Skill；
新增 Climate 领域模块、`.climate/` 状态和 `evals/climate/`。

### 3. 为什么不修改 QueryEngine？

QueryEngine 是通用模型—工具循环，Climate 状态属于业务层。通过 Tool 和 Repository 接入可降低
耦合与上游升级风险。

### 4. 最难的问题是什么？

跨进程长任务的一致性：多文件状态、并发写、进程崩溃、重复调用和跨会话恢复。

### 5. 去掉 LLM 还剩什么？

仍有结构化工具、状态机、Repository、恢复、安全和 Eval。LLM 只负责理解与编排。

### 6. OpenHarness Agent Loop 怎么运行？

用户消息 → compact 检查 → 模型请求携带 Tool schema → 模型返回 tool use → Hook → schema →
Permission → execute → tool result 回填 → 下一模型轮次 → 无工具调用时结束。

### 7. Tool schema 和校验在哪里？

`BaseTool.to_api_schema()` 把 Pydantic JSON Schema 发给模型；模型返回后 QueryEngine 再
`model_validate()`，业务语义由 Tool 内部校验。

### 8. ReAct、Plan-and-Execute、固定 Workflow 区别？

ReAct 灵活但不稳定；Plan-and-Execute 先规划再执行；固定 Workflow 最可靠。ClimWorkflow 是
“Agent 规划 + 确定性状态机执行”的混合模式。

### 9. 为什么 Context 不只放聊天历史？

聊天会 compact、截断和重启，也可能被模型错误总结。权威状态必须放版本化 RunContext。

### 10. Memory、对话和业务状态区别？

对话用于当前推理，Memory 用于导航和摘要，Climate Context 才决定 step、artifact 和 run 是否成功。

### 11. 如何防止模型跳过 plan？

不靠 Prompt，靠 Tool 在执行前检查持久化 plan、action、depends_on 和状态转换；非法调用不写 Context。

### 12. max_turns 用尽怎么办？

不猜状态。新会话先 read_context，再从持久化 step 继续。注意 QueryEngine 构造器默认 8，但应用
Settings 可以覆盖，Eval 必须冻结实际配置。

### 13. Tool 失败由谁重试？

普通业务失败返回模型决定；CDS 仅 timeout/rate-limit 在一次 step attempt 内最多重试 3 次，
不重复增加 attempts；永久错误不重试。

### 14. 为什么不用 Multi-Agent？

当前流程依赖明确、共享状态强，Multi-Agent 只会增加成本和一致性复杂度。证明有独立角色和并行收益
后再引入。

### 15. 为什么锁和 expected_version 都要？

锁串行化临界区；version 防止持有旧快照的调用方覆盖新状态。

### 16. 原子写等于事务吗？

不等于。原子写只保证单文件旧/新二选一；多文件一致性还需要锁、version 和 WAL。

### 17. Context 写完、index 没写就崩溃怎么办？

先写 active-run marker。恢复时根据文件事实补 index 或回滚 old active；未引用有效 run 列为 orphan。

### 18. 残留 running 为什么不能算成功？

running 只证明执行意图已持久化，不证明副作用完成。恢复时转为
`CLIMATE_INTERRUPTED`，清理 `.part` 后显式重试。

### 19. 幂等怎么做？

规范化输入后计算 SHA-256。成功 step 同 hash 直接返回且不改 version；不同 hash 返回幂等冲突。

### 20. 两进程同时更新怎么办？

固定顺序加 workspace/run lock，锁内重读并校验 version，冲突方重新读取而不是覆盖。

### 21. read_context 为什么不能偷偷恢复 WAL？

因为它声明只读，偷偷写文件会绕过 plan/default 权限。发现 WAL 返回
`CLIMATE_RECOVERY_REQUIRED`，由 mutating Tool 恢复。

### 22. 如何证明不会有两个 active run？

对事务每个故障点注入崩溃，重复 recovery，断言 active 唯一、恢复幂等、orphan 不自动激活。

### 23. 为什么 Pydantic 后还要业务校验？

Pydantic 校验类型和范围；跨字段互斥、DAG、依赖、状态和 artifact 一致性属于业务语义。

### 24. Permission 和 Climate Path Guard 为什么双重？

Permission 管用户授权和 fnmatch deny，不是完整路径沙箱；Climate Guard 在所有模式下强制
workspace、write zone、link escape 和文件类型。

### 25. Windows 路径有哪些坑？

`C:foo`、UNC、混合分隔符、junction、`CON/NUL/COM1`。要先词法拒绝，再检查 resolve 后真实边界。

### 26. 为什么 local 文件要复制？

避免源文件修改或删除导致历史结果漂移；复制后计算哈希，形成 run 自包含 artifact。

### 27. Hook 执行顺序？

PRE Hook 在 Registry、Pydantic、Permission、execute 之前；POST Hook 在副作用之后，只能观测，
不能回滚。

### 28. 如何证明 Hook 真阻断了工具？

断言 execute=0、Context version 不变、文件树不变、Trace 有 blocked provenance，目标字符串没写入报告。

### 29. 如何防止泄密？

输入和 details 用 allowlist；只存相对路径；Trace 脱敏；凭证只走外部配置；敏感路径全模式拒绝。

### 30. 为什么不能只看报告存在？

报告可能来自缓存、错误 fallback、跳步或伪造。还要检查工具序列、状态、版本、哈希和 Hook。

### 31. Synthetic 和 real offline 区别？

Synthetic 只测 schema/assertion/report wiring；real offline 调真实 Climate Tool 但禁网。两者都不等于
真实模型 baseline。

### 32. 如何判断工具序列正确？

Scenario 冻结 expected sequence，Trace 记录每次调用；硬断言顺序、依赖、错误码和最终 Context。

### 33. 为什么硬断言失败要非零退出？

让 CI 能把行为错误当成失败，而不是“只要生成报告就成功”。

### 34. 为什么真实模型跑 3 次、至少 2 次成功？

这是 smoke baseline，不是统计证明。它避免单次幸运成功，也容忍一次瞬时失败。

### 35. 换模型后 baseline 还能用吗？

不能。模型、Prompt、Tool schema、scenario、配置或 commit 改变都要重新跑。

### 36. LLM-as-Judge 有什么问题？

有偏好、非确定性、Prompt 注入和版本漂移。主观质量可 Judge；状态、哈希、序列和安全必须硬断言。

### 37. 怎么定位 Agent 失败？

按模型输入 → Hook/Registry/schema/Permission → Tool → Repository → 外部服务 → Eval assertion 分层定位。

### 38. CDS 下载为什么用 `.part`？

防止半文件被当成成功。下载到 `.part`，验证、fsync、hash 后 `os.replace`，失败不发布 artifact。

### 39. 怎么防止下载到 HTML 错误页？

检查非空、最小尺寸、文件头、magic、扩展名，并用真实科学数据解析库打开。

### 40. CSV、NetCDF、GRIB 区别？

CSV 是二维文本；NetCDF 适合多维科学数组和元数据；GRIB 是气象压缩消息格式。G2 只支持 CSV。

### 41. 经纬度、时间、单位怎么校验？

请求校验坐标范围、north>south、日期区间和变量 allowlist；数据校验坐标、单位、缺失值和经度体系。

### 42. 为什么 fallback 必须显式？

静默 sample 会伪造数据来源。只有用户开启且 timeout/rate-limit 耗尽重试时允许，并记录 provenance。

### 43. CDS timeout、限流、认证分别怎么办？

timeout/限流有限重试；认证和永久错误不重试、不 fallback；所有错误必须脱敏。

### 44. 为什么不用普通 DAG？

固定任务应该用 DAG。Agent 只在自然语言理解、参数补全、受约束选择和多轮恢复上有价值，执行正确性
仍由确定性 Pipeline 保证。

---

## 3. 30 秒项目介绍

### 当前 G0 版本

> 我正在基于 OpenHarness 开发 ClimWorkflow。OpenHarness 已有 Agent Loop、Tool、Permission、
> Hook 和 Compact，我计划在不修改 QueryEngine 语义的前提下，新增气象工具、版本化 Context、
> 状态机、WAL 恢复和 Eval。核心目标不是简单调用气象 API，而是验证长任务 Agent 如何做到安全、
> 可恢复和可评测。目前只完成规格设计，功能还不能算已实现。

### 完成后版本

只有自动化测试和验收通过后才能使用：

> 我基于 OpenHarness 扩展了一个可恢复气象工作流 Agent。我复用了通用 Agent Loop、Tool、
> Permission 和 Hook，新增 7 个领域 Tool、Context Repository、状态机、原子写、锁、WAL 和幂等，
> 并通过真实离线 Eval 检查工具序列、Context、artifact 哈希和 Hook 阻断。设计重点是让模型负责
> 理解与编排，让确定性系统负责执行正确性。

---

## 4. 五句兜底答案

1. **贡献边界**：我做的是 OpenHarness 二次开发，不把上游 Runtime 当作个人实现。
2. **状态原则**：聊天和 Memory 不是权威状态，RunContext 才是。
3. **可靠性原则**：原子写解决单文件完整性，锁、version 和 WAL 解决并发与多文件恢复。
4. **Agent 原则**：模型负责意图和编排，Tool 与状态机负责确定性执行。
5. **评测原则**：不只看最终回答，要硬断言工具序列、状态、artifact 和安全 provenance。

---

## 5. Day 15 求职交付（2026-09-01 实测，勿改数字）

### 两条简历 bullet

- 基于 OpenHarness 扩展可恢复气候数据 Agent：7 个类型化工具 + 磁盘 Context + 双锁/WAL/原子写；本机 Climate 258 collect、257 passed / 1 skipped（`climate_integration` 默认 skip）；四场景 `real_offline` 硬断言 `real_pass_rate=1.0`。
- G4 真实 CDS ERA5 最小 NetCDF smoke 1 passed（47.18s），固定模型 `deepseek-v4-pro` `real_agent` baseline 3/3 硬断言（独立 workspace，禁止 sample fallback）；凭证与下载数据不入库。

### 30 秒简介

ClimWorkflow 是跑在 OpenHarness 工具循环上的可恢复气候工作流。我不改 QueryEngine，用 7 个工具把 init→plan→acquire→inspect→plot→report 落到磁盘 Context。离线 MVP 用 sample/local；G4 才走真实 CDS 和真实模型，并且用硬断言而不是“模型说成功了”。

### 2 分钟架构

QueryEngine 调工具 → Climate Tool（Pydantic + 路径再校验）→ pipeline/状态机 → ContextRepository（workspace.lock 然后 run.lock，原子写，active-run WAL）。Eval 分三层：`real_offline` 真跑工具禁网；`synthetic_dry_run` 只测 wiring 且不计分；`real_agent` 固定配置跑 3 次至少 2 次全硬断言。

### 5 分钟讲解提纲

1. 问题：长任务 Agent 不能把聊天当权威状态。
2. 复用边界：不改 QueryEngine。
3. 七工具与状态机。
4. 路径安全与 `.cdsapirc` 全模式拒绝。
5. WAL/孤儿 run/幂等。
6. Eval 真实性：禁网、Hook provenance、3/3 baseline。
7. 限制：fork CI 已绿但未合入 HKUDS；Windows 上游 23 fail；不是通用调度器。

### 三个深挖问答

**WAL**：active-run 先写 marker，再写 Context/index，失败按文件事实补写或回滚；只读 `climate_read_context` 发现未完成事务返回 `CLIMATE_RECOVERY_REQUIRED`，不偷偷修。

**路径安全**：只接受 workspace 相对路径；解析后必须仍在 workspace；symlink 逃逸拒绝；错误脱敏；`.cdsapirc` 加入 `SENSITIVE_PATH_PATTERNS`。

**Eval 真实性**：`real_offline` 有 socket guard；synthetic 显著标记且 `counts_toward_real_pass_rate=false`；`real_agent` 无 config 直接拒绝；3 次独立 workspace，fingerprint 含 config/scenario/skill/commit。

### 一个真实失败与修复

G4 曾把“模型说完成了”和“磁盘 Context completed + CDS 无 fallback”分开。修复是硬断言 `cds_mode_no_fallback`、artifact manifest 与独立 workspace；少于 2/3 不发布成功 baseline。

### 下一步（不是空泛优化）

异步 CDS 任务、大数据分块 inspect、更多冻结 climate operation（例如风场分量合成图），而不是泛泛“提升性能”。

