---
name: climate-ds
description: >
  ClimWorkflow climate-data workflow guidance: 7-tool DAG order, optional
  read-only validate after report, disk Context recovery, credential safety,
  offline sample/local, and G4 CDS acquire.
---

# climate-ds

本 Skill 只提供 Agent 指导，不承载业务实现。工具执行、状态机和产物写入由 Climate
工具完成。

## 自然语言到四类动作

用户可以用自然语言描述目标。必须把目标写入 `climate_init_workflow.objective`，再规划
结构化 DAG。Climate 包不解析自由文本科学流程。`climate_plan_steps.action` 只能是：

- `acquire_data`
- `inspect_dataset`
- `analyze_plot`
- `write_report`

标准四步：acquire → inspect → plot → report。不得发明第五类 action，不得把 SPI / IVT / TC
等论文子步骤写成新的 plan action。

## 七工具顺序

必须按依赖顺序调用，不得跳步：

1. `climate_init_workflow` — 创建或显式 resume run，并切换 active run。
2. `climate_plan_steps` — 校验并持久化 DAG。
3. `climate_acquire_data` — 离线用 sample/local；G4 真实场景用 `mode=cds` 且 `allow_sample_fallback=false`。
4. `climate_inspect_dataset` — 有界检查，不修改源数据集。
5. `climate_analyze_plot` — 先 PNG，必要时真实 SVG。科学 NetCDF 用 histogram，y=t2m。
6. `climate_write_report` — inspect 与 plot 成功后再写报告。
7. `climate_read_context` — 只读、脱敏、有界的权威 Context 视图。

默认已注册 `climate_validate_artifacts`。建议在 `climate_write_report` 成功后调用，做只读
规则校验。它不是 plan action，不得当成第五类科学步骤；DAG 硬断言不强制调用。

## 数据模式选择

- `sample`：无密钥、离线演示 CSV。
- `local`：workspace 内已有 CSV。
- `cds`：真实 ERA5；禁止静默 fallback 到 sample。

## 遇错先读 Context

会话压缩、重启或工具报错后，必须先调用 `climate_read_context` 获取磁盘 Context。
磁盘 Context 是权威恢复来源。不得依赖 compact summary、对话记忆或猜测 run/step
已经成功。

## 凭证安全

禁止把 CDS 凭证、API key、token 或 `.cdsapirc` 写入工具输入、日志或 Context。
错误信息必须脱敏。不要读取 `~/.cdsapirc` 或 `~/.openharness/credentials.json`。

## 禁止事项

- 禁止声称可以增加 SPI / IVT / TC 或其他自由科学 action。
- 禁止建议执行任意 Python、Shell、`exec`/`eval` 或生成代码沙箱。
- 禁止 Selenium / 浏览器自动化抓取 CDS 门户。

## 范围

G0～G3 不调用 CDS，不要求真实模型，只使用离线 sample/local。
G4 真实 Agent baseline 必须走 CDS，禁止静默 fallback 到 sample。
workspace 外路径禁止。本 Skill 不是通用 DAG 调度器。
