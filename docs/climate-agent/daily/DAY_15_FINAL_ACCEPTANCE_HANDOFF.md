# Day 15：最终验收、文档收口与求职交付

## 今日目标

停止功能开发，对 G0～G4 做最终验收，形成可复现、可讲解、可安全提交的完整项目。

- **SPEC 需求**：全部适用需求、Definition of Done、PHASE-001、MODEL-001
- **预计投入**：6～8 小时
- **完成标志**：G0～G4 PASS；若外部 blocker 未解决，则诚实保持 G4 GAP、G3 MVP 仍成立
- **上一天**：[Day 14](DAY_14_G4_REAL_AGENT_BASELINE.md)

## 今日原则

- 不增加新功能。
- 先审查，再修 blocker/high。
- 不以真实网络偶发失败掩盖工程缺陷，也不以 mock 冒充真实 baseline。
- 不提交凭证、真实下载数据、缓存、`.part`、临时 workspace 或原始 Trace。
- 简历和 README 只写实测事实。

## 完整操作流程

### 1. 最终工作区清单（45 分钟）

```powershell
git status --short --branch
git diff --check
```

分类所有变更：

- Climate 源码。
- Climate 测试。
- Eval/Skill/文档。
- dependency/CI。
- baseline。
- 不应存在的缓存、凭证、下载数据和临时产物。

让 Cursor 扫描敏感模式，但不要打开/输出真实凭证文件。

### 2. 需求追踪审计（1 小时）

对 SPEC 第 16 节逐项生成：

```text
需求 ID
→ 实现文件/符号
→ 自动化测试 node ID
→ 最近命令结果
→ PASS/GAP
→ 风险/外部 blocker
```

规则：

- 没有实现或测试证据即 GAP。
- marked integration 未真实运行则相关真实要求 GAP。
- MODEL-001 未达 2/3 则 GAP。
- G4 GAP 不应破坏已验收的 G3 Offline Engineering MVP 称谓。

### 3. 最终验证矩阵（2～3 小时）

离线必跑：

```powershell
uv run pytest tests/test_climate -q
uv run pytest -q
uv run ruff check src tests scripts evals
uv run python -m evals --suite climate --mode real_offline
uv run python -m evals --suite climate --mode synthetic_dry_run
git diff --check
```

有明确凭证/网络许可时再跑：

```powershell
uv run pytest -m climate_integration tests/test_climate/test_cds.py -q
```

检查 baseline：

- 3 次独立运行。
- ≥2 次全部硬断言通过。
- 配置一致。
- 失败记录保留。
- 无敏感字段。

### 4. 最终只读审查（45 分钟）

要求 Cursor 按以下维度输出 blocker/high/medium/low：

- 路径与凭证安全。
- Context schema/迁移/并发/原子写/WAL。
- 状态机/幂等/失败恢复。
- 工具 schema/权限/依赖顺序。
- Eval 真实性与 synthetic 隔离。
- CDS retry/fallback/format。
- 文档可复现性。
- 阶段外修改与上游回归。

### 5. 只修 blocker/high（1～2 小时）

每项先复现、再最小修复、再运行受影响测试和最终离线矩阵。真实集成相关修复后，若用户允许网络，
重新运行对应 marker；修改 baseline 配置/代码后必须重新进行 3 次 baseline。

### 6. 文档与求职材料收口（1 小时）

README 最终包含：

- 问题背景和产品边界。
- 架构与关键数据流。
- 7 个工具和状态机。
- 安全、并发、恢复机制。
- Offline/real Eval 区别。
- 安装、Demo、测试、恢复。
- 真实支持矩阵和已知限制。
- 实测指标及生成命令。

准备面试材料：

1. 30 秒项目概述。
2. 2 分钟架构。
3. 5 分钟完整讲解。
4. 三个深挖点：WAL、路径安全、Eval 真实性。
5. 一个真实失败案例及修复。
6. 下一步：异步任务、大数据分块、更多 climate operation，而不是泛泛“优化性能”。

## 今日主 Prompt

```text
执行 ClimWorkflow Day 15：最终验收和交付。

今天禁止新增功能。
先阅读 SPEC 全文，重点第 15～18 节和 DAY_15_FINAL_ACCEPTANCE_HANDOFF.md。

步骤：
1. 分类完整 git status/diff，识别源码、测试、文档、baseline 和不应存在的产物。
2. 建立全部需求 ID→实现→真实测试 node ID→结果→PASS/GAP 矩阵。
3. 运行 Climate、全量 pytest、Ruff、real_offline、synthetic 和 diff check。
4. 仅在用户已允许网络/准备凭证时运行 climate_integration，不读取/回显凭证。
5. 审查 baseline 是否满足固定配置 3 次、至少 2 次硬断言通过。
6. 做 blocker/high/medium/low 只读审查。
7. 只修 blocker/high，每项先有复现测试。
8. 重跑最终矩阵，回填 SPEC 与 README 的真实状态和指标。
9. 输出最终验收报告、剩余 GAP、风险和简历证据。

不虚构 G4 PASS，不提交凭证/数据/缓存，不自动提交或推送。
```

## 分步骤 Prompt

```text
只读生成最终需求追踪矩阵。没有真实 node ID、integration 或 baseline 证据的项必须标 GAP。
```

```text
执行最终离线验证矩阵，记录 collected/passed/skipped/failed、场景结果与耗时，不立即修复。
```

```text
对当前变更做安全与工程审查，按 blocker/high/medium/low 输出；重点检查凭证、路径、WAL、fallback 和 Eval 真实性。
```

```text
根据报告只修 blocker/high，禁止新增功能。任何 baseline 相关代码变化后提醒三次真实运行必须重新开始。
```

```text
基于最终真实结果生成：两条简历 bullet、30 秒简介、5 分钟讲解提纲、三个面试深挖问答。不要编造指标。
```

## 最终验收清单

- [ ] 全部离线测试、全量回归、Ruff 通过。
- [ ] real_offline 四场景通过。
- [ ] 默认测试/CI 禁网。
- [ ] 真实 integration 有明确运行证据或诚实 GAP。
- [ ] MODEL-001 有 3 次/2 次通过证据或诚实 GAP。
- [ ] 所有 PASS 均有实现和测试 node ID。
- [ ] 无凭证、真实数据、缓存、临时文件和绝对路径。
- [ ] README 可从空 workspace 复现。
- [ ] 简历数字全部可复核。

## 提交与推送（必须分开授权）

人工确认最终验收后，才发送：

```text
请提交当前已验收修改。先检查完整 status、diff 和最近提交风格；只暂存 ClimWorkflow 相关源码、
测试、Eval、Skill、文档和脱敏 baseline；排除凭证、真实数据、缓存与运行产物；提交后检查 status。
不要推送。
```

确认提交正确后，再单独决定是否推送；禁止 force push。

## 最终报告模板

```text
ClimWorkflow 15 天最终报告：
- 当前 commit/分支：
- G0/G1/G2/G3/G4：
- Climate pytest：
- 全量 pytest：
- Ruff：
- real_offline：
- climate_integration：
- 真实 Agent baseline：
- blocker/high 修复：
- 剩余 GAP：
- 安全检查：
- 可复现 Demo：
- 实测简历指标：
- 是否可提交：
- 是否建议推送：
```
