# Day 10：离线工程 MVP 总验收与求职证据

## 今日目标

停止增加功能，完成 G3 总验收、只修 blocker/high，并形成可复核的简历项目证据包。

- **SPEC 需求**：G0～G3 全部适用需求、PHASE-001、DOC-001、CI-001
- **预计投入**：6～8 小时
- **完成称谓**：仅在全部通过后称为 **ClimWorkflow Offline Engineering MVP**
- **上一天**：[Day 09](DAY_09_G3_HOOK_SKILL_README.md)
- **下一天**：[Day 11](DAY_11_G4_TECHNICAL_SPIKE.md)

## 今日禁止事项

- 不增加新工具、新数据格式、新 UI、CDS 或真实模型。
- 不为了获得好看数字删除失败测试或降低硬断言。
- 不虚构测试数量、成功率、性能或“生产级”结论。
- 不自动提交/推送；人工验收后另行请求。

## 完整操作流程

### 1. 工作区与范围审计（45 分钟）

```powershell
git status --short --branch
git diff --check
```

让 Cursor 对照 SPEC 列出：

- G0～G3 每个需求 ID。
- 实现文件。
- 实际测试 node ID。
- 当前 PASS/GAP。
- 阶段外文件、缓存、凭证、运行产物。

搜索并确认无 `.env`、`.cdsapirc`、token、API key、绝对本机路径进入变更。

### 2. 四层验证（2～3 小时）

第一层，Climate：

```powershell
uv run pytest tests/test_climate -q
```

第二层，OpenHarness 全量：

```powershell
uv run pytest -q
```

第三层，质量：

```powershell
uv run ruff check src tests scripts evals
git diff --check
```

第四层，真实离线 Eval：

```powershell
uv run python -m evals --suite climate --mode real_offline
uv run python -m evals --suite climate --mode synthetic_dry_run
```

记录真实：

- 测试 collected/passed/skipped/failed。
- 4 个场景结果及耗时。
- 7 工具序列。
- artifact 数量和摘要验证。
- 多轮恢复最终状态。
- Hook blocked provenance。

### 3. 只读验收与定级（45 分钟）

Prompt 要求输出 blocker/high/medium/low。判断规则：

- blocker：安全逃逸、Context 损坏、恢复错误、硬断言虚假、全链路不可运行。
- high：主要工具契约错误、幂等/锁/原子写缺陷、文档不可复现。
- medium/low：不影响 MVP 契约的可维护性或表达问题。

### 4. 只修 blocker/high（1～2 小时）

每个修复：

1. 先添加/确认复现测试。
2. 最小修复。
3. 运行受影响测试。
4. 重新运行四层验证。

不顺手重构。

### 5. SPEC 与文档收口（45 分钟）

- 第 16 节回填实际 node ID 与 PASS。
- G3 DoD 全部满足后更新称谓。
- README 中测试数字使用本次真实结果。
- 明确 G4 未完成，不写“支持真实 ERA5/CDS”。

### 6. 求职证据包（1 小时）

建议在 README/docs 中保留：

- 一张清晰架构图：Agent loop → 7 Tools → Repository/State → `.climate/` → Eval。
- 一段 3～5 分钟 Demo 脚本。
- 一份真实 Eval 输出样例（脱敏、不含临时绝对路径）。
- 关键工程取舍：Memory ≠ Context、PRE Hook guard、WAL、SVG fallback、synthetic ≠ real。
- 真实指标清单。

简历表述模板（数字必须替换为实测）：

```text
基于 OpenHarness 从零设计并实现可恢复的气候数据 AI Agent，构建 7 个类型化工具与版本化工作流
状态机，通过原子写、双层文件锁、乐观并发控制和 WAL 恢复保障任务一致性；建立覆盖路径攻击、
多轮恢复与 Hook 拦截的离线 Eval，完成 X 个测试、4 个硬断言场景，真实离线场景通过率 X%。
```

面试讲解顺序：

```text
为什么不能只靠聊天上下文
→ Context/状态机设计
→ 文件安全和并发一致性
→ 7 工具如何受依赖与幂等约束
→ Eval 如何证明真实执行
→ 失败案例与工程取舍
```

## 今日主 Prompt

```text
执行 ClimWorkflow Day 10：G0～G3 Offline Engineering MVP 总验收。

今天不增加任何功能。
先对照 SPEC 第 16～18 节，建立“需求 ID→实现→实际测试 node ID→结果”清单。
依次运行：
- uv run pytest tests/test_climate -q
- uv run pytest -q
- uv run ruff check src tests scripts evals
- uv run python -m evals --suite climate --mode real_offline
- uv run python -m evals --suite climate --mode synthetic_dry_run

然后做只读审查，按 blocker/high/medium/low 输出。
只修 blocker/high；每个修复先有复现测试，修复后重跑四层验证。
仅当全部适用需求 PASS 后更新 SPEC 和 MVP 称谓。

输出真实测试/场景/耗时指标和简历证据，不虚构数字。
不接入 G4，不访问旧目录，不提交、不推送。
```

## 分步骤 Prompt

```text
只读建立 G0～G3 需求追踪清单。任何没有真实 node ID 的 PASS 都降为 GAP，不修复。
```

```text
执行四层验收并保存摘要。失败时先定位到需求 ID，不立即扩大修复范围。
```

```text
根据验收报告只修 blocker/high。禁止新增功能或清理无关技术债。
```

```text
基于真实测试与 Eval 输出，起草两条中文简历 bullet 和 5 分钟面试讲解提纲；所有数字必须注明来源。
```

## MVP 验收清单

- [ ] G0～G3 所有适用需求 PASS。
- [ ] Climate 与全量 pytest 通过。
- [ ] Ruff、diff check 通过。
- [ ] 三个核心真实离线场景和 Hook guard 通过。
- [ ] sample/local Demo 可从空 workspace 复现。
- [ ] 多轮恢复只依赖 Context。
- [ ] 无凭证、缓存、绝对路径或临时 Eval 产物。
- [ ] README 不夸大 G4 能力。
- [ ] 简历指标全部可由命令输出复核。

## 是否允许提交

只有人工确认上述清单后，另开请求：

```text
请提交 G1～G3 已验收的 Offline Engineering MVP 修改。先检查完整 status/diff/最近提交风格；
只暂存相关文件，不提交凭证、缓存或 Eval 运行产物；提交后验证 status，不推送。
```

## 日终报告模板

```text
Day 10 / MVP Gate：
- Climate pytest：
- 全量 pytest：
- Ruff：
- real_offline 场景与耗时：
- synthetic 标记：
- blocker/high 及修复：
- G0～G3 PASS/GAP：
- MVP 称谓是否成立：
- 实测简历指标：
- G4 开始条件：
```
