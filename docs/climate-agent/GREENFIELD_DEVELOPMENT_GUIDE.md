# ClimWorkflow Greenfield 开发手册

> 用途：在干净 Fork `E:\agent\ClimWorkflow` 中，基于 OpenHarness 官方源码从零开发 ClimWorkflow。
>
> 本手册既是执行流程，也是可逐阶段复制给 Cursor Agent 的 Prompt 集。

---

## 0. 项目边界

### 正式开发仓库

```text
本地目录：E:\agent\ClimWorkflow
个人远程：git@github.com:Hongjian01/OpenHarness.git
官方上游：git@github.com:HKUDS/OpenHarness.git
开发分支：feat/climworkflow-mvp
上游基线：9b2efd795c6aa09f88b0c257d269a9e518da6ae7
```

### Greenfield 约束

1. 不复制 `E:\agent\OpenHarness` 中旧的 Climate 源码、Eval 源码和测试。
2. 旧目录只用于理解历史需求，不作为实现来源。
3. OpenHarness 官方已有的 Engine、Tools、Hooks、Permissions、Memory 等能力可以直接复用。
4. 每个功能按 `SPEC → 失败测试 → 实现 → 回归 → PASS` 开发。
5. 未通过阶段验收门，不进入下一阶段。
6. 默认不提交、不推送；完成一阶段并人工检查后，再单独要求 Agent 创建提交。

---

## 1. 每次开始工作前

在 Cursor 中打开：

```text
E:\agent\ClimWorkflow
```

执行：

```powershell
git status --short --branch
git remote -v
git branch --show-current
```

预期：

```text
当前分支：feat/climworkflow-mvp
origin：Hongjian01/OpenHarness
upstream：HKUDS/OpenHarness
工作区：无意外修改
```

首次开始时可推送远程开发分支：

```powershell
git push -u origin feat/climworkflow-mvp
```

---

## 2. 统一 SDD 执行规则

将下面 Prompt 放在每个开发阶段 Prompt 之前：

```text
你正在 E:\agent\ClimWorkflow 仓库中开发 ClimWorkflow。

必须遵守：
1. 当前项目是基于 upstream/main 的 Greenfield 实现，不复制旧目录 E:\agent\OpenHarness 的 Climate 代码。
2. 先阅读 docs/climate-agent/SPEC.md 和当前阶段相关的 OpenHarness 官方代码。
3. 不凭记忆假设 OpenHarness API；必须以当前仓库代码为准。
4. 每个 MUST 需求先写失败测试，再写最小实现。
5. 不修改与当前阶段无关的模块。
6. 不执行 git commit、git push、rebase 或远程写操作，除非我单独明确要求。
7. 不写入或提交 API Key、CDS Token、.env、.cdsapirc。
8. 完成后运行相关测试和最小必要回归测试。
9. 汇报：修改文件、满足的需求 ID、测试结果、未完成项和风险。
10. 如果 SPEC 与当前代码冲突，停止实现并说明冲突，不得自行改变契约。
```

---

## 3. Phase G0：重新基线化规格

**目标**：在新仓库建立真正适用于 Greenfield 开发的 SPEC。

**预计时间**：0.5～1 天。

### 执行 Prompt

```text
执行 ClimWorkflow Phase G0：重新基线化规格。

仓库：E:\agent\ClimWorkflow
上游基线：9b2efd795c6aa09f88b0c257d269a9e518da6ae7

任务：
1. 广泛检查当前仓库中可复用的 OpenHarness 模块：
   - engine/query.py、query_engine.py
   - tools/base.py、tools/__init__.py
   - hooks、permissions、memory、compact
   - settings、atomic_write_text、exclusive_file_lock
   - 当前测试结构和 CI 配置
2. 确认当前仓库没有 Climate、Climate Eval 和 Climate 测试实现。
3. 创建 docs/climate-agent/SPEC.md，版本为 v0.1 Greenfield Candidate。
4. SPEC 必须包含：
   - 产品目标、非目标
   - upstream commit 和目标仓库
   - REUSE / EXTEND / NEW 矩阵
   - Context Schema、状态机、错误模型
   - 安全路径、原子写、锁和恢复契约
   - 工具输入输出契约
   - Phase G0～G4
   - 需求 ID—测试追踪矩阵
   - Definition of Done
5. 所有 Climate 实现项初始标记为 GAP，不能声称已完成。
6. 不创建 Climate 源码，不写测试，不迁移旧代码。

完成后只汇报 SPEC 评审摘要和待决问题。
```

### G0 验收门

- [ ] SPEC 明确绑定新仓库与 upstream commit。
- [ ] 不存在“7 个工具已完成”等旧 PoC 声明。
- [ ] 官方能力和新开发能力分类有代码证据。
- [ ] 每个 MUST 有需求 ID。
- [ ] 每个需求 ID 有预定测试。
- [ ] 开放决策已冻结或明确阻塞开发。

建议在 G0 完成后单独发起一次评审：

```text
只读评审 docs/climate-agent/SPEC.md。
逐项对照当前仓库源码，检查合理性、可行性、技术准确性和 SDD 完整性。
按 blocker/high/medium/low 输出问题。
不要修改文件，也不要开始代码开发。
```

---

## 4. Phase G1：核心状态基础

**目标**：建立安全、可持久化、可测试的工作流内核。

**预计时间**：2～3 天。

### 建议模块

```text
src/openharness/climate/
  __init__.py
  errors.py
  paths.py
  models.py
  repository.py
  state.py

tests/test_climate/
  test_paths.py
  test_models.py
  test_repository.py
  test_state.py
```

### G1-A：安全路径与错误模型 Prompt

```text
执行 Phase G1-A：安全路径和结构化错误。

范围：
- 新建 climate/errors.py
- 新建 climate/paths.py
- 新建 tests/test_climate/test_paths.py
- 只实现 SPEC 中 PATH、SEC 路径相关需求

测试必须覆盖：
- 正常 workspace 相对路径
- ../ 路径穿越
- 绝对路径
- Windows 混合分隔符
- UNC 路径
- symlink/junction 逃逸（平台支持时）
- 错误信息不泄露用户主目录

严格先写失败测试，再实现。
完成后运行相关测试和 linter，不实现 Context 或工具。
```

### G1-B：Context Schema 与 Repository Prompt

```text
执行 Phase G1-B：版本化 Context Repository。

范围：
- climate/models.py
- climate/repository.py
- repository/model 单元测试

实现：
- schema_version、version、created_at、updated_at
- run/step 状态枚举
- Context 序列化和反序列化
- atomic_write_text
- workspace lock + run lock，固定锁顺序
- expected_version 冲突检测
- 损坏 JSON 错误
- v1→当前 Schema 迁移和备份
- active_run 写入事务与 orphan 恢复

不得实现领域工具。
测试必须包含故障注入、重复 run_id、版本冲突和损坏 Context。
```

### G1-C：状态机 Prompt

```text
执行 Phase G1-C：工作流状态机。

依据 SPEC 的状态转换表实现 climate/state.py。

要求：
- 合法转换成功
- 非法转换返回稳定错误码
- 重复请求符合幂等规则
- 失败时保持最后稳定状态
- context 不可写时不得尝试二次记录错误
- plan step 状态与 attempts 规则可测试

只修改 state/models/repository 必要接口和对应测试。
```

### G1 验收门

- [ ] 路径攻击测试通过。
- [ ] Context 原子写、迁移、冲突和损坏恢复测试通过。
- [ ] 状态转换测试通过。
- [ ] 无 Climate 业务工具也能独立测试工作流内核。
- [ ] 对应需求由 GAP 更新为 PASS。

---

## 5. Phase G2：离线工作流 MVP

**目标**：完成无需 API Key/CDS 的端到端气候工作流。

**预计时间**：2～3 天。

### 建议模块

```text
src/openharness/climate/
  pipeline.py
  tools.py
  registry.py

tests/test_climate/
  test_pipeline.py
  test_tools.py
  test_registry.py
```

### G2-A：最小纵切 Prompt

```text
执行 Phase G2-A：第一个离线纵向切片。

只实现：
1. climate_init_workflow
2. climate_plan_steps 的标准四步 plan
3. climate_acquire_data 的 sample 模式
4. climate_inspect_dataset 的 CSV 模式
5. climate_read_context
6. 测试内独立 ToolRegistry 注册

端到端目标：
init → plan → sample acquire → inspect → read context

约束：
- 所有写入通过 Context Repository 和安全路径解析器
- inspect 不修改数据文件，但可以写 workflow result/event
- 不实现 local、CDS、plot、report
- 7 个工具完成前不修改 create_default_tool_registry
- 不修改 QueryEngine

先写工具链失败测试，再实现。
```

### G2-B：完整离线工具链 Prompt

```text
执行 Phase G2-B：补齐离线 ClimWorkflow 工具。

增加：
- climate_acquire_data local 模式
- climate_analyze_plot
- climate_write_report

完成：
init → plan → acquire(sample/local) → inspect → plot → report → read context

要求：
- 完成 7 个工具后一次性接入 create_default_tool_registry，禁止静默覆盖同名工具
- plot/report 只能写 .climate/output/
- acquire 只能写 .climate/data/
- matplotlib 缺失时有确定性降级策略
- 每个工具有 Pydantic Schema、结构化错误和状态转换测试
- 重复调用符合 SPEC 幂等规则
```

### G2 验收门

- [ ] 7 个工具通过 registry 暴露。
- [ ] sample/local 流水线不需要外部 API。
- [ ] 端到端测试验证数据、图、报告和 Context。
- [ ] 非法工具顺序和非法路径被拒绝。
- [ ] OpenHarness 原有测试没有回归。

---

## 6. Phase G3：Eval、恢复与 Agent 包装

**目标**：让 MVP 可评测、可恢复、可展示。

**预计时间**：2～3 天。

### 执行 Prompt

```text
执行 Phase G3：ClimWorkflow Eval 与恢复能力。

先检查当前 upstream 是否已有可复用 Eval 基础；不得假设旧目录 evals/ 存在。

设计并实现最小必要能力：
- Climate scenario schema
- TraceRecord
- hard assertions
- 离线 runner
- sample pipeline scenario
- cached inspect scenario
- multiturn recovery scenario
- Hook 事件采集和 output guard scenario
- climate-ds Skill

要求：
- dry-run 必须明确它验证什么、不验证什么
- 真实工具离线运行和合成 dry-run 结果分开
- Hook scenario 必须证明是 Hook 拦截，而不是工具自身拒绝
- Eval 产物包含 run_id、工具序列、错误码、耗时和最终状态
- 不接入真实 CDS
```

### G3 验收门

- [ ] 三个核心 scenario 真实执行通过。
- [ ] 多轮恢复场景通过。
- [ ] Hook 事件有硬断言。
- [ ] Skill 可被 OpenHarness 加载。
- [ ] README 可以复现离线 Demo。

达到 G3 后，可称为：

```text
ClimWorkflow Offline Engineering MVP
```

---

## 7. Phase G4：真实数据与真实模型

**目标**：接入 CDS/ERA5 和真实 Agent Eval。

**预计时间**：3～5 天。

### 执行 Prompt

```text
执行 Phase G4：真实 CDS/ERA5 数据层。

要求：
- 新增 CdsRequestInput
- dataset/variables/area/date/format 校验
- cdsapi optional dependency
- .part 临时文件 + 成功后原子替换
- 只对 timeout/rate-limit 重试
- 默认禁止静默 fallback
- 显式 fallback 时记录 requested_mode/effective_mode/fallback_reason
- NetCDF/GRIB 扩展名与内容一致
- CDS 凭证不得进入日志、Trace、Context 或 Git
- mock 测试不依赖网络
- 真实集成测试使用 pytest marker，默认 CI 跳过

完成后运行固定模型配置的真实 Agent smoke 三次，至少两次通过，并写 baseline。
```

---

## 8. 每阶段结束后的检查 Prompt

```text
请对当前阶段做只读验收：

1. 对照 docs/climate-agent/SPEC.md 列出本阶段需求 ID。
2. 检查每项需求是否有实现和自动化测试。
3. 运行阶段测试、Climate 回归测试及必要的 OpenHarness 原有测试。
4. 检查是否存在越界修改、硬编码凭证、未处理异常或文档漂移。
5. 给出 PASS/GAP 清单。
6. 不修复、不提交，先输出验收报告。
```

发现问题后再使用：

```text
根据上一份验收报告，只修复其中 blocker/high 问题。
不得扩大范围，不提交代码。
修复后重新运行受影响测试并汇报。
```

---

## 9. 提交 Prompt

人工确认阶段验收通过后，单独发送：

```text
请提交当前阶段已验收的修改。

要求：
- 先检查 git status、完整 diff 和最近提交风格
- 只暂存当前阶段相关文件
- 不提交凭证、缓存、Eval 临时运行产物
- 使用聚焦“为什么”的提交信息
- 提交后运行 git status 验证
- 不推送远程
```

确认提交正确后再发送：

```text
将当前 feat/climworkflow-mvp 分支推送到 origin，不进行 force push。
```

---

## 10. 时间预算

| 阶段 | 内容 | 全职时间 |
|------|------|----------|
| G0 | Greenfield SPEC + 评审 | 0.5～1 天 |
| G1 | 路径、错误、Context、状态机 | 2～3 天 |
| G2 | 7 工具 + 离线流水线 | 2～3 天 |
| G3 | Eval、恢复、Hook、Skill | 2～3 天 |
| **离线工程化 MVP** | **G0～G3** | **7～10 天** |
| G4 | CDS、NetCDF、真实模型 baseline | 3～5 天 |
| **真实数据版本** | **G0～G4** | **10～15 天** |

---

## 11. MVP 最终验收

离线 MVP 必须能够从空 workspace 执行：

```text
用户任务
  → 初始化 run
  → 生成结构化 plan
  → sample/local 取数
  → 数据质检
  → 生成图表
  → 生成报告
  → 持久化 Context
  → 错误后读取 Context 恢复
  → Eval 自动断言产物和轨迹
```

最终命令以 Greenfield SPEC 中冻结的命令为准，至少包括：

```powershell
python -m pytest tests/test_climate -q
uv run python -m evals --suite climate
```

只有所有当前阶段需求为 PASS，且满足 Definition of Done，才进入下一阶段。

---

## 12. 从现在开始

下一次新对话在 `E:\agent\ClimWorkflow` 中发送：

```text
请先阅读 docs/climate-agent/GREENFIELD_DEVELOPMENT_GUIDE.md。
现在只执行 Phase G0：重新基线化规格。
不要开始 Climate 代码开发，不要复制旧目录代码，不要提交或推送。
```
