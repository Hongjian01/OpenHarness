# Day 11：G4 技术 Spike 与 DEC-G4-001 冻结

## 今日目标

在写真实 CDS 代码前，用最小可重复实验关闭 DEC-G4-001：冻结科学数据依赖、格式校验、
ERA5 allowlist 和 CI 安装策略。

- **SPEC 需求**：DEC-G4-001、CDS-001/002 的设计前置、TEST-006、PHASE-001
- **预计投入**：6～8 小时
- **完成标志**：决策有实验数据和 fixture 支撑，SPEC 已评审冻结，G4 才允许进入实现
- **上一天**：[Day 10](DAY_10_MVP_ACCEPTANCE_PORTFOLIO.md)
- **下一天**：[Day 12](DAY_12_G4_CDS_RELIABLE_DOWNLOAD.md)

## 开始条件

- Day 10 Offline Engineering MVP Gate 必须 PASS。
- G0～G3 应有稳定 checkpoint；若尚未提交，由用户决定是否先单独提交。
- 今日默认不需要 CDS 凭证、不访问真实网络。

## 今日要回答的决策

1. NetCDF 读取库及最小版本/optional extra。
2. GRIB 读取库及其系统依赖、Windows/Linux 可安装性。
3. 不完整/伪装文件的 magic/content 校验方法。
4. ERA5 dataset allowlist 和每个 dataset 的 variable allowlist 来源。
5. 测试 fixture 的许可证、大小与生成方式。
6. `climate_integration` marker 注册和默认 CI 禁网方式。
7. 本地真实集成如何显式启用，如何避免凭证进入日志。

## 完整操作流程

### 1. 基线与只读研究（1 小时）

```powershell
git status --short --branch
uv run pytest tests/test_climate -q
```

让 Cursor 检查当前 `pyproject.toml`、CI、Python 3.10/3.11 和 Windows 环境。若需要查询依赖最新状态，
明确使用官方文档来源，记录访问日期；不要仅凭模型记忆指定版本。

候选评估至少包含：

- NetCDF：xarray + 可用 backend，或更小直接 reader。
- GRIB：cfgrib/eccodes 的系统依赖和 CI 成本。
- magic：HDF5/NetCDF classic/GRIB 标识与解析器二次验证。

### 2. 先定义 spike 验收（30 分钟）

在写实验前列出可判定结果：

- Python 3.10/3.11 可安装。
- 当前 Windows 开发环境能读取最小 fixture。
- Linux CI 有明确安装路径。
- 读取后可得到变量、维度、时间/经纬坐标。
- 错扩展名、截断和随机 bytes 均被拒绝。
- fixture 足够小且可合法进入测试。

### 3. 最小实验（2～3 小时）

Spike 代码只能放临时位置或明确 `scripts/` 实验文件；决策后删除无价值实验。不得把 spike 当生产实现。

分别验证：

- 正常 NetCDF fixture。
- 正常 GRIB fixture（若本机依赖可用）。
- 文件扩展名与 content 不一致。
- 截断内容。
- optional dependency 缺失时的可诊断错误。

若 GRIB 在 Windows/CI 安装成本不可接受，允许冻结为“G4 先支持 NetCDF，GRIB 明确 GAP”，但必须先
修订 SPEC/CDS format 契约并评审，不能实现后偷偷降级。

### 4. Marker 与 CI 设计（45 分钟）

设计并测试：

- `pyproject.toml` 注册 `climate_integration`。
- 默认 `uv run pytest -q` 不访问网络。
- 真实测试必须同时满足 marker + 显式环境开关/凭证可用。
- 缺凭证时 skip reason 清楚，不显示路径或 token。

今天可先写 collection/marker 失败测试，但不写真实 CDS client。

### 5. 冻结决策（1～1.5 小时）

更新 SPEC 第 14、18 节：

- 最终依赖及选择理由。
- 支持格式和明确 GAP。
- allowlist 版本/来源。
- magic + parser 双重校验。
- CI/default skip。
- DEC-G4-001 状态改为已关闭。

先让 Cursor 做只读评审，确认决策不破坏 G0～G3 optional dependency 属性。

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
执行 ClimWorkflow Day 11：关闭 DEC-G4-001 技术决策。

先确认 Day 10 MVP Gate PASS。阅读 SPEC 第 13、14、18 节和 DAY_11_G4_TECHNICAL_SPIKE.md。

今天不实现 CDS client。
先用当前 Python/Windows/CI 约束评估 NetCDF/GRIB 候选依赖，并通过最小 fixture spike 验证：
- 安装与读取
- 变量/维度/坐标
- magic/content/扩展名一致性
- 截断/伪装文件拒绝
- optional dependency 缺失行为

依赖版本必须依据当前官方来源或包管理器，不得凭记忆编造。
冻结 allowlist、fixture、pytest marker 和默认 CI 禁网策略。
最后更新 SPEC 关闭 DEC-G4-001，并做只读评审。

不读取凭证、不访问真实 CDS、不提交、不推送。
如果 GRIB 不可行，停止并提出明确的 SPEC 范围修订，不静默省略。
```

## 分步骤 Prompt

```text
只读比较候选 NetCDF/GRIB 依赖，按 Python3.10/3.11、Windows、Linux CI、安装体积、读取能力、许可证和失败模式输出决策表，不编辑文件。
```

```text
为最小 spike 写明确验收断言，再执行实验；不要把实验脚本当生产模块。
```

```text
只读评审 DEC-G4-001 决策：检查是否有证据、是否保留 offline optional、是否明确 GRIB/NetCDF 支持边界。
```

## 验收清单

- [ ] Day 10 Gate PASS。
- [ ] 依赖选择有实测，不靠记忆。
- [ ] NetCDF/GRIB 支持边界明确。
- [ ] magic/content 校验策略可测试。
- [ ] allowlist 有来源和版本。
- [ ] marker 注册与默认禁网策略明确。
- [ ] SPEC 已关闭 DEC-G4-001 或明确阻塞 Day 12。

## 风险与止损

- 不因 15 天工期强行承诺不可安装的 GRIB 依赖。
- 不把真实凭证用于技术 spike。
- 依赖安装失败连续超过 2 小时，停止试错，记录证据并收缩/修订 G4 契约。

## 日终报告模板

```text
Day 11 / DEC-G4-001：
- 候选与最终依赖：
- Windows/Linux/Python 兼容：
- fixture/magic 实验：
- allowlist 来源：
- marker/CI 策略：
- SPEC 修订：
- 决策关闭：是/否
- Day 12 是否允许开始：
```

## Day 11 冻结记录（2026-08-30）

工作区：分支 `feat/climworkflow-mvp`。未读取 `.cdsapirc` / `.env`，未访问真实 CDS，未提交、未推送。
依赖版本来自 PyPI JSON 与 CDS Catalogue，检索日期 2026-08-30。

```text
Day 11 / DEC-G4-001：
- 候选与最终依赖：NetCDF 用 netCDF4>=1.7.4（不采用最新 xarray：requires-python>=3.11；不采用 h5netcdf 作主 reader）。GRIB 用 eccodes>=2.48.0（不钉 cfgrib/xarray）。cdsapi>=0.7.7 仅 extra climate。
- Windows/Linux/Python 兼容：本机 Windows Python 3.13 安装 netCDF4==1.7.4、eccodes==2.48.0；selfcheck Found: ecCodes v2.48.0。netCDF4 有 cp310-win_amd64 与 manylinux wheel；eccodeslib 2.48.0.26 有 manylinux_2_28 cp310/cp311。CI 3.10/3.11 有明确 wheel 路径。
- fixture/magic 实验：minimal_t2m.nc 8884B HDF5/NetCDF4 可读 t2m+time/lat/lon；minimal.grib 179B 可读 shortName=t 与经纬角点；截断/随机/错扩展名拒绝。
- allowlist 来源：CDS collection reanalysis-era5-single-levels form JSON 2026-08-30；DOI 10.24381/cds.adbb2d47；8 个大气单层变量；排除浪场。
- marker/CI 策略：climate_integration 已注册；默认 CLIMATE_INTEGRATION!=1 则 skip；Actions 设 0；不读凭证文件。
- SPEC 修订：第 14/18 节关闭 DEC-G4-001；format 保持 netcdf|grib，未降级。
- 决策关闭：是
- Day 12 是否允许开始：是（允许写 CDS client；仍禁止在未评审情况下改依赖或省略 GRIB）
```
