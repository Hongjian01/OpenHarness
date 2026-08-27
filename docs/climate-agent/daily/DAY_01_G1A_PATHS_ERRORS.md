# Day 01：G1-A 安全路径与结构化错误

## 今日目标

在不实现 Context、状态机或业务工具的前提下，建立所有后续文件访问都必须经过的安全边界。

- **SPEC 需求**：PATH-001、PATH-002、PATH-003、SEC-001、ERR-001/002（共享错误基础）、
  SDD-001、TEST-001
- **预计投入**：6～8 小时
- **完成标志**：路径攻击测试和错误脱敏测试全部通过；没有 Climate 业务工具
- **前置文件**：`docs/climate-agent/SPEC.md`
- **下一天**：[Day 02](DAY_02_G1B_CONTEXT_REPOSITORY.md)

## 严格范围

允许新增：

```text
src/openharness/climate/__init__.py
src/openharness/climate/errors.py
src/openharness/climate/paths.py
tests/test_climate/test_errors.py
tests/test_climate/test_paths.py
```

禁止：

- 不创建 models/repository/state/tools/pipeline。
- 不修改 QueryEngine、PermissionChecker 或默认 registry。
- 不访问或复制 `E:\agent\OpenHarness`。
- 不提交、不推送，不写凭证。

## 开始前检查（15 分钟）

在 Cursor 新对话中先发送“今日主 Prompt”，再让 Agent 执行：

```powershell
git status --short --branch
git branch --show-current
git rev-parse HEAD
```

人工确认：

- 分支是 `feat/climworkflow-mvp`。
- HEAD 基线仍可追溯到 `9b2efd795c6aa09f88b0c257d269a9e518da6ae7`。
- 除 `docs/climate-agent/` 外没有意外修改。
- Agent 已阅读 SPEC 第 5、9、13、16 节。

要求 Agent 只读检查：

```text
src/openharness/sandbox/path_validator.py
src/openharness/permissions/checker.py
src/openharness/tools/base.py
tests/test_sandbox/test_path_validator.py
tests/test_permissions/test_checker.py
```

## 完整开发流程

### 1. 冻结 API（30 分钟）

先让 Cursor 给出设计，不编辑文件：

- ClimateError 数据结构和固定错误码映射。
- 成功/失败 JSON envelope 的确定性序列化方式。
- workspace 相对输入到安全绝对 Path 的内部转换流程。
- Windows drive-relative、UNC、混合分隔符、保留设备名判定。
- 不存在目标的父链 realpath 检查策略。

如设计与 SPEC 冲突，停止开发并报告，不自行改契约。

### 2. RED：先写失败测试（1.5～2 小时）

只创建测试，至少覆盖：

- 正常相对文件、嵌套目录和固定 `.climate/` 写入区。
- `..`、`.`、空段、NUL、`~`。
- POSIX/Windows 绝对路径、`C:relative`、UNC。
- `/` 与 `\` 混合造成的绕过。
- `CON`、`NUL`、`COM1` 等 Windows 保留名。
- symlink/junction 逃逸；平台不支持时使用明确 skip。
- 错误输出不含 home、workspace 绝对路径、token 或 traceback。
- 共享 envelope 的 `ok/error` 结构和确定性 JSON；完整 ToolResult 一致性留到 G2 工具存在后验证。

运行并保存预期失败摘要：

```powershell
uv run pytest tests/test_climate/test_errors.py tests/test_climate/test_paths.py -q
```

如果测试意外通过，说明测试没有约束到新实现，先修测试。

### 3. GREEN：最小实现（2～3 小时）

实现顺序：

1. `errors.py`：错误码、ClimateError、安全 message/details、成功/失败 envelope。
2. `paths.py`：词法拒绝。
3. 解析 workspace 和候选路径。
4. realpath/common-path 边界校验。
5. 固定 data/output/state write zone 校验。
6. 错误脱敏。

每完成一个小步骤只运行对应测试；不要提前扩展未来工具 API。

### 4. VERIFY：回归与静态检查（1 小时）

```powershell
uv run pytest tests/test_climate/test_errors.py tests/test_climate/test_paths.py -q
uv run pytest tests/test_sandbox/test_path_validator.py tests/test_permissions/test_checker.py -q
uv run ruff check src/openharness/climate tests/test_climate
git diff --check
git status --short
```

随后让 Cursor 做只读验收，重点检查：

- 是否存在 TOCTOU 明显漏洞。
- 错误是否泄露绝对路径。
- 是否错误复用了只能做 fnmatch 的 PermissionChecker。
- 是否出现阶段外文件。

## 今日主 Prompt

```text
你正在 E:\agent\ClimWorkflow 执行 Day 01 / Phase G1-A。

先阅读：
- docs/climate-agent/SPEC.md
- docs/climate-agent/daily/DAY_01_G1A_PATHS_ERRORS.md
- 当前仓库相关 OpenHarness 路径与权限代码

只实现：PATH-001、PATH-002、PATH-003、SEC-001、ERR-001/002 的共享错误基础、SDD-001、TEST-001。
ERR-001 的全部工具一致性在 G2 前保持 GAP。

严格顺序：
1. 先只读确认现有 API 和今日范围。
2. 先写 tests/test_climate/test_errors.py 与 test_paths.py。
3. 运行测试并确认 RED。
4. 再最小实现 errors.py、paths.py。
5. 运行今日测试、相关 OpenHarness 回归和 Ruff。
6. 做只读验收并汇报需求 ID、测试 node ID、结果、风险。

不得实现 Context、Repository、状态机或业务工具。
不得访问旧目录，不提交、不推送。
SPEC 与代码冲突时停止并报告。
```

## 分步骤 Prompt

### RED Prompt

```text
现在只编写 Day 01 失败测试，不写实现。逐项映射 PATH/SEC/ERR 需求，运行测试证明失败，并解释每个失败为何符合预期。
```

### GREEN Prompt

```text
根据刚才的失败测试，按 errors.py → paths.py 顺序写最小实现。不要修改测试来迁就实现，不增加今日范围外抽象。
```

### 验收 Prompt

```text
只读验收 Day 01。逐项检查 PATH-001/002/003、SEC-001、ERR-001/002 共享基础、TEST-001；
ERR-001 完整工具一致性保持 GAP。列出 PASS/GAP、实际测试 node ID、越界修改和安全风险。不要修复。
```

## 验收清单

- [ ] 先看到与需求对应的 RED。
- [ ] 所有路径攻击用例通过。
- [ ] symlink/junction 测试有真实断言或明确平台 skip。
- [ ] 错误 envelope 稳定、可 JSON 解析且已脱敏。
- [ ] 设备/FIFO/socket 属于 Day 05 PATH-004，今日没有提前实现或宣称 PASS。
- [ ] 没有 Context、状态机或工具代码。
- [ ] Ruff 和相关 OpenHarness 回归通过。
- [ ] 只有验证通过的需求才可在 SPEC 追踪矩阵中改为 PASS。

## 风险与止损

- Windows junction 难以稳定构造时，不得删除该要求；保留平台条件测试并记录验证环境。
- 若必须修改 PermissionChecker 才能通过，说明设计越界，停止并评审。
- 首次 `uv run` 若生成新的锁文件，必须在日终作为范围变化报告，不得默认提交。
- 预计超时 2 小时时，优先完成 PATH-001/002、SEC-001、ERR-001；PATH-003 不得用不安全占位实现。

## 日终报告模板

```text
Day 01 结果：
- 修改文件：
- RED 证据：
- PASS 需求 ID：
- GAP 需求 ID：
- 测试命令与结果：
- Ruff：
- 安全风险：
- 阶段外修改：无/说明
- Day 02 阻塞项：
```
