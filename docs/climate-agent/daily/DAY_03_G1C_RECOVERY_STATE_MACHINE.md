# Day 03：G1-B/C 迁移、事务恢复与状态机

## 今日目标

补齐 Context 恢复能力和严格状态机，完成 G1 验收门。

- **SPEC 需求**：MIG-001、REC-001/002/003、STATE-001/002/003、IDEM-001、LOCK-001、CON-001、TEST-002/003、PHASE-001
- **预计投入**：7～9 小时
- **完成标志**：G1 所有适用需求通过只读验收；无业务工具也能完整测试内核
- **上一天**：[Day 02](DAY_02_G1B_CONTEXT_REPOSITORY.md)
- **下一天**：[Day 04](DAY_04_G2A_OFFLINE_VERTICAL_SLICE.md)

## 严格范围

允许新增/修改：

```text
src/openharness/climate/models.py
src/openharness/climate/repository.py
src/openharness/climate/state.py
src/openharness/climate/errors.py
tests/test_climate/fixtures/（仅 v1/损坏/恢复 fixture）
tests/test_climate/test_models.py
tests/test_climate/test_repository.py
tests/test_climate/test_state.py
docs/climate-agent/SPEC.md（仅验收后回填状态/node ID）
```

禁止创建 tools/pipeline/registry；禁止为了赶工跳过故障注入。

## 开始前检查

```powershell
git status --short --branch
uv run pytest tests/test_climate/test_errors.py tests/test_climate/test_paths.py tests/test_climate/test_models.py tests/test_climate/test_repository.py -q
```

若 Day 01/02 有失败，先让 Cursor只修 blocker/high，再开始今日任务。

## 完整开发流程

### 1. RED：v1 迁移与备份（1 小时）

先建立固定 v1 fixture，测试：

- 补 event sequence、计算现存 artifact sha256。
- 迁移前备份原始字节到固定 backups 区域。
- 备份失败中止，原文件不变。
- artifact 缺失返回 `CLIMATE_MIGRATION_FAILED`。
- 重复迁移幂等，不重复破坏性处理。

### 2. RED：active-run WAL 与 orphan（1～1.5 小时）

参数化每个故障点：

1. marker 发布前。
2. marker 已发布、run Context 未写。
3. run Context 已写、index 未写。
4. index 已写、marker 未删。
5. marker 删除失败后再次恢复。

断言：

- 最终最多一个 active run。
- 恢复重复执行结果一致。
- 有效 orphan 只列出，不自动激活。
- `resume_run_id` 只激活指定有效 orphan。
- 损坏 Context 原字节不变；不可写时不二次记录错误。

### 3. GREEN：迁移与恢复（1.5～2 小时）

实现时固定：

- 所有动作在 workspace → run 锁序下完成。
- marker 自身也原子写。
- 按文件事实补写或回滚，不按“最新时间”猜 active run。
- 清理失败不掩盖已完成事务，但留下可再次恢复的证据。

运行：

```powershell
uv run pytest tests/test_climate/test_repository.py -q
```

### 4. RED：状态机（1～1.5 小时）

在 `test_state.py` 参数化 SPEC 第 8 节：

- 所有合法 run/step 转换。
- 所有未列出的非法转换。
- attempts 只在进入 running 时 +1。
- 每次真实转换 event sequence +1。
- succeeded + 同 input hash 重放无版本变化。
- succeeded + 不同输入返回幂等冲突。
- 残留 running 恢复为 failed/CLIMATE_INTERRUPTED。
- Context 不可写时返回原持久化错误，不递归记录。
- 失败操作保留最后稳定状态。

### 5. GREEN：状态机最小实现（1.5 小时）

状态机只计算/校验转换；持久化统一委托 Repository。不要让状态机直接写文件或执行领域副作用。

### 6. G1 全量验收（1～1.5 小时）

```powershell
uv run pytest tests/test_climate/test_errors.py tests/test_climate/test_paths.py tests/test_climate/test_models.py tests/test_climate/test_repository.py tests/test_climate/test_state.py -q
uv run pytest tests/test_utils/test_fs.py tests/test_swarm/test_lockfile.py tests/test_sandbox/test_path_validator.py tests/test_permissions/test_checker.py -q
uv run ruff check src/openharness/climate tests/test_climate
git diff --check
git status --short
```

让 Cursor 做一次只读 G1 验收。只有真实通过的需求才在 SPEC 第 16 节从 GAP 改 PASS，并填入真实
node ID。更新 SPEC 后再次运行 `git diff --check`。

## 今日主 Prompt

```text
执行 ClimWorkflow Day 03：完成 Phase G1-B/C 并通过 G1 验收门。

阅读 SPEC 第 6～9、13、15～18 节和 DAY_03_G1C_RECOVERY_STATE_MACHINE.md。

严格顺序：
1. 先为 MIG-001、REC-001/002/003 写失败测试。
2. 实现 v1→v2 备份迁移、active-run WAL、orphan 显式恢复。
3. 再为 STATE-001/002/003、IDEM-001 写参数化失败测试。
4. 实现纯状态机，并通过 Repository 持久化。
5. 运行 G1 全量测试、相关 OpenHarness 回归和 Ruff。
6. 只读验收；仅对真实 PASS 项回填 SPEC。

不得实现任何 Climate 业务工具，不访问旧目录，不提交、不推送。
任何故障注入失败、锁序不明确或 SPEC 冲突都视为 blocker。
```

## 分步骤 Prompt

```text
现在只写 active-run 事务的故障注入测试。列出每个 crash point 的磁盘前置状态、恢复动作和最终不变量，不写实现。
```

```text
现在只实现迁移和恢复，使现有 RED 变 GREEN。禁止自动选择最新 orphan，禁止损坏文件兜底为空对象。
```

```text
现在只写状态机转换表测试。对未在 SPEC 表中的转换统一断言 CLIMATE_INVALID_TRANSITION 且零副作用。
```

```text
对 G1 做只读验收。按需求 ID 输出 PASS/GAP、测试 node ID、失败注入覆盖、锁序证据、阶段外文件和 blocker/high。不要修复。
```

## 验收清单

- [ ] v1 迁移有原始字节备份且幂等。
- [ ] WAL 每个故障点均可恢复。
- [ ] orphan 不会被自动激活。
- [ ] 状态转换、attempts、events、幂等全部可测试。
- [ ] Context 不可写时无二次写错误。
- [ ] G1 测试和必要回归全通过。
- [ ] 尚无 Climate 业务工具。
- [ ] SPEC 只对有证据的需求改 PASS。

## 风险与止损

- 今日是关键路径；若超时，不能进入 Day 04。优先保证 REC-002 和 STATE-001 正确，而不是写空实现过门。
- 多文件事务无法获得文件系统级原子性，因此 WAL 恢复测试是强制项。
- 如果发现 SPEC 的 v1 fixture 无法无损迁移，停止并提出规格修订，不猜字段。

## 日终报告模板

```text
Day 03 / G1 Gate：
- 修改文件：
- 迁移测试：
- WAL 故障点：
- 状态机测试：
- PASS/GAP 需求与 node ID：
- Climate + 回归 + Ruff：
- G1 验收：PASS/GAP
- Day 04 是否允许开始：是/否
- 阻塞项：
```
