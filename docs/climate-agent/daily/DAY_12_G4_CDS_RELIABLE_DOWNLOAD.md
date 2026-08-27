# Day 12：G4 CDS 输入与可靠下载

## 今日目标

实现严格 CdsRequestInput、optional cdsapi、受控重试和 `.part` 原子下载发布；全部自动测试使用 mock。

- **SPEC 需求**：SEC-002、CDS-001、CDS-002、CDS-003、TEST-006
- **预计投入**：7～8 小时
- **完成标志**：mock 覆盖成功、缺依赖、超时、限流、永久错误、内容无效与凭证脱敏
- **上一天**：[Day 11](DAY_11_G4_TECHNICAL_SPIKE.md)
- **下一天**：[Day 13](DAY_13_G4_FORMAT_INSPECTION_FALLBACK.md)

## 开始条件

DEC-G4-001 已关闭并通过评审。未关闭时停止。

## 凭证安全红线

- 今日单元测试不需要真实 token。
- 不创建/读取/打印 `.cdsapirc`。
- 不让用户通过 Tool 输入传 API key/token。
- exception、日志、Trace、Context 不保存 cdsapi 原始凭证错误。
- 按 SPEC 将 `.cdsapirc` 加入不可覆盖的敏感路径规则，并测试所有权限模式。

## 严格范围

允许新增/修改：

```text
src/openharness/climate/cds.py（或 Day 11 冻结的模块名）
src/openharness/climate/models.py
src/openharness/climate/tools.py
src/openharness/permissions/checker.py（仅 .cdsapirc 敏感规则）
pyproject.toml（仅冻结的 optional dependency/marker）
tests/test_climate/test_cds.py
tests/test_permissions/test_checker.py
```

今天不实现 inspect NetCDF/GRIB 或 sample fallback。

## 完整开发流程

### 1. RED：CdsRequestInput（1 小时）

测试：

- dataset/variables 只允许 Day 11 allowlist。
- variables 非空、去重、规范顺序。
- area 为 north/west/south/east，范围合法且 north > south。
- ISO 日期、start≤end、最长 366 天。
- format 只允许冻结格式。
- 未知字段、凭证字段、mode 字段冲突拒绝。
- 序列化不含 secret。

### 2. GREEN：输入模型（1 小时）

实现跨字段 validator；错误 details 只包含字段名/允许值，不回显敏感原始内容。

### 3. RED：下载状态机（1.5～2 小时）

使用 fake cds client，不联网：

- cdsapi 缺失 → `CLIMATE_DEPENDENCY_MISSING`。
- 成功下载先落 `.part`，校验后 `os.replace`。
- 发布 artifact 前文件非空、magic/content 与 extension 一致。
- timeout/rate-limit 最多 3 次并验证退避调用。
- auth/invalid request/server permanent error 不重试。
- 每次失败清理 `.part`，不发布 artifact。
- 重试不重复增加 step attempts（一次工具 attempt 内的传输重试）。
- 日志/错误/Context/Trace 不含 fake secret。
- `SENSITIVE_PATH_PATTERNS` 在 default/plan/full_auto 拒绝 `.cdsapirc`。

退避测试 monkeypatch sleep，不真实等待。

### 4. GREEN：可靠下载（2 小时）

分层：

1. `CdsClientProtocol`/adapter，便于 mock。
2. 错误分类，只识别 timeout/rate-limit 可重试。
3. 有界指数退避，最多 3 次。
4. 下载至同目录唯一 `.part`。
5. Day 11 冻结的格式校验。
6. fsync/replace。
7. 成功后交给 Repository/状态机记录。

工具层默认 `allow_sample_fallback=false`，今天所有失败均返回错误，不 fallback。

### 5. 验证

```powershell
uv run pytest tests/test_climate/test_cds.py tests/test_permissions/test_checker.py -q
uv run pytest tests/test_climate -q
uv run pytest -q
uv run ruff check src tests scripts evals
git diff --check
git status --short
```

确认默认测试期间无网络连接；可添加网络 guard。

## 今日主 Prompt

```text
执行 ClimWorkflow Day 12 / Phase G4：CDS 输入与可靠下载。

前置：先证明 DEC-G4-001 已关闭。阅读 SPEC 第 5、9、10.4、13、14、16、18 节和
DAY_12_G4_CDS_RELIABLE_DOWNLOAD.md。

严格先写失败测试：
1. CdsRequestInput allowlist/area/date/format/未知字段/凭证字段。
2. fake cds client 的成功、缺依赖、timeout、rate-limit、永久错误。
3. .part、magic/content、原子 replace、失败清理。
4. `.cdsapirc` 在全部权限模式下拒绝。
5. secret 不进入日志、Context、Trace、ToolResult。

再最小实现模型、CDS adapter、错误分类、最多3次退避和原子下载。
所有测试使用 mock，默认禁网；不实现 inspect 或 fallback。
不打印/读取凭证，不提交、不推送。
```

## 分步骤 Prompt

```text
只写 CdsRequestInput 失败测试，加入 api_key/token 等禁止字段，逐项映射 CDS-001。
```

```text
只写 fake client 下载测试，用 monkeypatch 验证重试次数和 sleep 序列，不真实联网/等待。
```

```text
实现下载 adapter；异常分类必须基于明确类型/状态，不用宽泛字符串把所有错误当可重试。
```

```text
对 Day 12 做安全审查：搜索 secret、.cdsapirc、绝对路径、原始 exception 和残留 .part，不修复。
```

## 验收清单

- [ ] 请求模型严格、allowlist 已冻结。
- [ ] cdsapi 是 optional dependency。
- [ ] 只重试 timeout/rate-limit，最多 3 次。
- [ ] `.part` 校验后才原子发布。
- [ ] 永久错误不重试、不 fallback。
- [ ] 默认测试禁网。
- [ ] `.cdsapirc` 全权限模式拒绝。
- [ ] 无凭证泄露。

## 风险与止损

- 不通过解析器/magic 的文件绝不发布，即使 HTTP/CDS 调用“成功”。
- cdsapi 异常类型不稳定时建立窄 adapter 映射并用 fixture 固化，禁止 catch-all 重试。
- 如果需要真实凭证才能完成单元测试，设计有误，停止。

## 日终报告模板

```text
Day 12：
- CdsRequestInput：
- optional dependency：
- mock 成功/重试/永久失败：
- .part/格式/原子发布：
- `.cdsapirc` 权限：
- 脱敏与禁网：
- PASS/GAP 需求：
- Day 13 blocker：
```
