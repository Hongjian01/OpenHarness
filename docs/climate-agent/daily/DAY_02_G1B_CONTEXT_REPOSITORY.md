# Day 02：G1-B Context Schema 与 Repository 主干

## 今日目标

建立可严格校验、确定性序列化、原子持久化并支持乐观并发控制的 Context Repository 主干。

- **SPEC 需求**：CTX-001、CTX-002、CTX-003、IO-001、LOCK-001、CON-001、ERR-001、SDD-001、TEST-002
- **预计投入**：7～8 小时
- **完成标志**：v2 Context round-trip、原子写、锁与 expected_version 测试通过
- **上一天**：[Day 01](DAY_01_G1A_PATHS_ERRORS.md)
- **下一天**：[Day 03](DAY_03_G1C_RECOVERY_STATE_MACHINE.md)

## 严格范围

允许新增/修改：

```text
src/openharness/climate/models.py
src/openharness/climate/repository.py
src/openharness/climate/errors.py
src/openharness/climate/paths.py
tests/test_climate/test_models.py
tests/test_climate/test_repository.py
```

今日暂不实现：

- v1→v2 迁移、active-run WAL 和 orphan 恢复留到 Day 03。
- 状态转换服务留到 Day 03。
- 不实现任何 Climate Tool。

## 开始前检查

```powershell
git status --short --branch
uv run pytest tests/test_climate/test_errors.py tests/test_climate/test_paths.py -q
```

让 Cursor 只读检查并引用当前 API：

```text
src/openharness/utils/fs.py
src/openharness/utils/file_lock.py
src/openharness/config/settings.py 中 lock + atomic write 用法
tests/test_utils/test_fs.py
tests/test_swarm/test_lockfile.py
```

确认 Day 01 无 blocker；若路径解析器仍有 GAP，不开始 Repository。

## 完整开发流程

### 1. 模型设计复核（45 分钟）

对照 SPEC 第 5～7 节列出：

- WorkspaceIndex 字段与不变量。
- RunContext v2、Step、Artifact、Event、结构化 error。
- enum、UUID v4、UTC RFC3339、event sequence、artifact 引用校验。
- `extra="forbid"` 和确定性 JSON 输出。
- Repository 公共方法、内部 expected_version 参数和锁责任边界。

先输出接口草案，不编辑文件；避免把 ToolResult 模型混入持久化模型。

### 2. RED：模型测试（1～1.5 小时）

在 `test_models.py` 先写：

- 最小合法 WorkspaceIndex/RunContext v2。
- 完整 round-trip 字节/对象一致性。
- 非 UUID、非 UTC、非法 enum、重复 step/artifact、断裂依赖/引用拒绝。
- event sequence 不连续拒绝。
- 未知字段拒绝。
- version 初始值与时间关系。

```powershell
uv run pytest tests/test_climate/test_models.py -q
```

确认测试因模型尚未实现而失败。

### 3. GREEN：实现模型（1.5～2 小时）

只实现通过模型测试所需的 Pydantic v2 模型、validator 和序列化函数。禁止加入迁移兼容分支。

### 4. RED：Repository 测试（1.5 小时）

在 `test_repository.py` 先写：

- 创建固定 `.climate/` 目录布局。
- 新建/读取 index 和 run Context。
- `atomic_write_text` 被调用，输出 UTF-8、两空格、稳定键顺序、末尾换行。
- `os.replace` 故障时旧文件保持原样、临时文件清理。
- expected_version 匹配时 +1；不匹配不改变文件。
- lock unavailable 转稳定错误。
- 两个并发写者不丢更新、不死锁。
- 不存在、损坏 JSON、不支持 schema 返回不同错误且不覆盖。

```powershell
uv run pytest tests/test_climate/test_repository.py -q
```

### 5. GREEN：Repository 主干（1.5～2 小时）

实现最少接口：

1. workspace/run 路径构造必须经过 Day 01 安全模块。
2. lock context：workspace → run 固定顺序。
3. load：读取、JSON 解析、严格 model validation。
4. save：锁内重读、expected_version、版本递增、原子写。
5. 错误统一转 ClimateError，禁止 traceback/绝对路径进入外部消息。

今日可以保留明确的私有扩展点供 Day 03 使用，但不得写假的迁移/恢复成功逻辑。

### 6. VERIFY（45 分钟）

```powershell
uv run pytest tests/test_climate/test_models.py tests/test_climate/test_repository.py -q
uv run pytest tests/test_utils/test_fs.py tests/test_swarm/test_lockfile.py -q
uv run pytest tests/test_climate/test_errors.py tests/test_climate/test_paths.py -q
uv run ruff check src/openharness/climate tests/test_climate
git diff --check
git status --short
```

## 今日主 Prompt

```text
执行 ClimWorkflow Day 02 / Phase G1-B：Context Schema 与 Repository 主干。

先阅读 SPEC 第 5～9、13、16 节和 DAY_02_G1B_CONTEXT_REPOSITORY.md，并检查当前 fs/file_lock API。

今日只实现 CTX-001/002/003、IO-001、LOCK-001、CON-001、ERR-001、TEST-002 中的模型、原子持久化、锁和版本冲突部分。

必须：
1. 先写 test_models.py 失败测试并运行 RED。
2. 最小实现 models.py。
3. 再写 test_repository.py 失败测试并运行 RED。
4. 最小实现 repository.py 主干。
5. 运行 Climate 测试、fs/lock 回归和 Ruff。

今日不要实现迁移、active-run 事务、orphan 恢复、状态机或业务工具。
不复制旧代码，不提交、不推送。冲突时停止报告。
```

## 分步骤 Prompt

```text
只设计 models/repository 公共接口和锁责任边界，不编辑文件。逐字段对照 SPEC，指出所有需要跨字段 validator 的不变量。
```

```text
现在只写模型失败测试。测试必须证明未知字段、断裂引用、非法时间/UUID/version/sequence 被拒绝。
```

```text
现在只写 Repository 失败测试，使用 monkeypatch 做 os.replace/lock 故障注入，并证明旧文件不被破坏。
```

```text
只读验收 Day 02：检查是否真正复用 atomic_write_text/exclusive_file_lock，锁序、expected_version、确定性 JSON 和错误脱敏是否符合 SPEC。不要修复。
```

## 验收清单

- [ ] 模型严格拒绝未知/不一致数据。
- [ ] Context 是唯一权威业务状态。
- [ ] Repository 不使用直接 `Path.write_text` 发布状态。
- [ ] expected_version 冲突完全无副作用。
- [ ] 并发测试无丢更新、无死锁。
- [ ] 损坏输入不被空 Context 覆盖。
- [ ] 今日没有迁移、恢复、状态机或工具。

## 风险与止损

- 若并发测试在 Windows 不稳定，分别保留线程/进程策略并记录平台；不得删除并发契约。
- 不要让 Repository 自动吞掉 Pydantic 错误；应映射为稳定错误码。
- 如果 schema 设计与 SPEC 示例冲突，停止并先评审 SPEC。

## 日终报告模板

```text
Day 02 结果：
- 模型/API：
- RED 证据：
- PASS/GAP 需求：
- 原子写/锁/并发测试：
- 版本冲突测试：
- 回归与 Ruff：
- Day 03 待完成：迁移、WAL、orphan、状态机
- 阻塞项：
```
