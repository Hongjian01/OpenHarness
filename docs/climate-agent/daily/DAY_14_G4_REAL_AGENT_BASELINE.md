# Day 14：G4 真实 CDS 与固定模型 Baseline

## 今日目标

在用户显式准备凭证并允许网络后，运行真实 CDS smoke 与固定 Agent 配置 3 次，形成可复核 baseline。

- **SPEC 需求**：CDS-001/002/003/004、SEC-001/002、MODEL-001、TEST-006
- **预计投入**：6～8 小时（受外部服务延迟影响）
- **完成标志**：3 次固定配置中至少 2 次满足全部硬断言，并保存脱敏 baseline
- **上一天**：[Day 13](DAY_13_G4_FORMAT_INSPECTION_FALLBACK.md)
- **下一天**：[Day 15](DAY_15_FINAL_ACCEPTANCE_HANDOFF.md)

## 用户必须先完成的外部准备

Agent 不得替用户创建、读取或回显凭证。由用户在本机按 CDS 官方方式配置：

- 有效 CDS 账号和许可。
- 标准外部凭证配置。
- 允许本次显式网络访问。
- 真实模型 provider/API 配置。
- 确认测试下载的区域/日期足够小，避免不必要配额与等待。

若任一条件缺失：跳过真实运行并报告明确 blocker，不能用 synthetic/mock 冒充 baseline。

## 预期文件

```text
evals/configs/climate-real.json
evals/baselines/climate-real-<commit>.json
evals/climate/runner.py（仅 real_agent adapter、3-run 聚合和原子 baseline）
tests/test_climate/test_evals.py
```

先用离线失败测试固定：`--runs` 必须为 3、少于 2 次通过不发布成功 baseline、失败 run 保留、
代码/config/scenario 变化使计数失效、配置和输出均不含凭证。

## 安全检查

运行前：

```powershell
git status --short --branch
uv run pytest tests/test_climate -q
uv run pytest -q
uv run ruff check src tests scripts evals
```

确认：

- `.gitignore` 不会遗漏运行产物，但不要依赖 ignore 保护凭证。
- trace/log/context 不包含 credential 字段。
- `.cdsapirc` 被 PermissionChecker 全模式拒绝。
- integration marker 默认不运行。

开始真实 API/Agent 测试前，要求 Cursor 读取并遵循仓库内
`.claude/skills/harness-eval/SKILL.md`，以当前技能定义的真实调用、环境隔离和结果记录方式为准。

## 完整操作流程

### 1. 真实 CDS 最小 smoke（1～2 小时）

先使用最小请求：

- 1 个冻结 dataset。
- 1 个变量。
- 1 天。
- 小区域。
- 优先冻结的 NetCDF 格式。
- `allow_sample_fallback=false`。

显式运行 marker；准确命令以 Day 11 冻结的环境开关为准，例如：

```powershell
uv run pytest -m climate_integration tests/test_climate/test_cds.py -q
```

验证：

- requested/effective mode 均为 cds。
- 非空、magic/content/extension 正确。
- Context/Trace/artifact 摘要一致。
- 无 `.part` 残留。
- 日志无凭证或 home 绝对路径。

如果服务限流/超时，验证重试后停止；不要无限重跑。

### 2. 冻结 Agent Baseline 配置（30 分钟）

三次运行必须完全一致：

- git commit/工作区版本标识。
- provider、model、温度/effort、max_turns。
- system prompt/Skill 版本。
- scenario、数据请求和 timeout。
- 权限模式。

baseline 只记录非敏感配置，不记录 key/base credential。

### 3. 运行前硬断言（30 分钟）

每次都要求：

- 工具顺序符合依赖。
- 无未知/非法工具。
- final status=completed。
- Context version 合法。
- requested/effective mode=cds；本场景禁止 fallback。
- dataset/plot/report 存在且摘要匹配。
- Trace 无 secret。
- 总耗时在 timeout 内。

### 4. 连续运行 3 次（2～3 小时）

使用 SPEC 冻结入口（PowerShell 的 `<commit>` 替换为实际短 commit）：

```powershell
uv run python -m evals --suite climate --mode real_agent `
  --agent-config evals/configs/climate-real.json `
  --runs 3 `
  --baseline-out evals/baselines/climate-real-<commit>.json
```

为每次使用独立空 workspace 和 run_id，禁止复用上一次成功 Context。记录：

- run index。
- started/finished/duration。
- tool sequence。
- assertion results。
- final status/version。
- 失败稳定错误码。

一次失败后不要改配置再继续计入同一 baseline；如果修改代码/配置，三次计数重新开始。

### 5. 写 Baseline（1 小时）

建议路径：

```text
evals/baselines/climate-real-<commit>.json
```

内容：

- suite/spec/schema 版本。
- git commit 或明确 dirty 状态（正式 baseline 应为可识别版本）。
- 非敏感固定配置。
- 三次独立结果。
- `passes >= 2` 硬断言。
- 失败原因，不删除失败 run。

临时数据文件不提交；baseline JSON 本身必须脱敏、使用相对 artifact 描述。

### 6. 验证

```powershell
uv run pytest tests/test_climate -q
uv run pytest -q
uv run ruff check src tests scripts evals
git diff --check
git status --short
```

## 今日主 Prompt

```text
执行 ClimWorkflow Day 14：真实 CDS smoke 与固定模型 baseline。

先阅读 SPEC 第 12～18 节和 DAY_14_G4_REAL_AGENT_BASELINE.md。
真实 API/Agent 测试前必须读取并遵循 .claude/skills/harness-eval/SKILL.md。
先检查用户是否已显式准备 CDS/模型凭证并允许网络；不要读取、打印或写入凭证。
若未准备，停止并报告 blocker，不得用 mock/synthetic 冒充。

顺序：
1. 运行默认离线测试和 Ruff，确认稳定。
2. 用最小 CDS 请求显式运行 climate_integration，fallback=false。
3. 检查数据格式、摘要、Context/Trace 和脱敏。
4. 先写并运行 real_agent runner 的 3-run/2-pass/不发布失败 baseline 测试。
5. 冻结 provider/model/config/scenario。
6. 通过 SPEC 固定 CLI 在三个独立空 workspace 连续运行真实 Agent smoke。
7. 任何配置/代码变化都使三次重新计数。
8. 至少 2/3 通过全部硬断言后写脱敏 baseline。
9. 重跑默认全量回归。

不得无限重试、不得提交真实数据/凭证/临时产物，不提交、不推送。
```

## 分步骤 Prompt

```text
只做运行前安全检查，列出凭证/网络/配额需要用户确认的项。不要主动查找凭证。
```

```text
执行最小真实 CDS smoke；只返回非敏感状态、错误码、耗时和相对 artifact 信息。
```

```text
冻结 baseline 配置并输出 hash/摘要。接下来三次运行不得改变任何配置。
```

```text
审查 baseline JSON：检查三次独立性、2/3 硬断言、失败 run 保留、无 secret/绝对路径/真实数据。
```

## 验收清单

- [ ] 用户显式提供外部准备和网络许可。
- [ ] 最小真实 CDS 请求成功，且 fallback=false。
- [ ] 三次运行配置一致、workspace 独立。
- [ ] 至少 2 次通过所有硬断言。
- [ ] 代码/配置变化后重新计数。
- [ ] baseline 保留失败结果且完全脱敏。
- [ ] 默认 CI/pytest 仍不访问网络。

## 风险与止损

- CDS 服务不可用、许可未接受或 quota 拒绝是外部 blocker，不通过降低断言解决。
- 限流只按实现策略重试，达到上限即停止。
- 若当日无法完成真实运行，Day 15 可用于重试一次；不得把项目状态标成 G4 PASS。

## 日终报告模板

```text
Day 14：
- 用户外部准备：完成/阻塞
- 真实 CDS smoke：
- 固定模型配置摘要：
- Run 1：
- Run 2：
- Run 3：
- 通过率：
- baseline 路径：
- 脱敏检查：
- MODEL-001：PASS/GAP
- Day 15 blocker：
```
