---
name: climate-ds
description: >
  ClimWorkflow climate-data workflow guidance: 7-tool order, disk Context
  recovery, credential safety, and G0-G3 offline limits without CDS.
---

# climate-ds

本 Skill 只提供 Agent 指导，不承载业务实现。工具执行、状态机和产物写入由 Climate
工具完成。

## 七工具顺序

必须按依赖顺序调用，不得跳步：

1. `climate_init_workflow` — 创建或显式 resume run，并切换 active run。
2. `climate_plan_steps` — 校验并持久化 DAG。
3. `climate_acquire_data` — G0～G3 仅使用 sample 或 local CSV。
4. `climate_inspect_dataset` — 有界检查，不修改源数据集。
5. `climate_analyze_plot` — 先 PNG，必要时真实 SVG。
6. `climate_write_report` — inspect 与 plot 成功后再写报告。
7. `climate_read_context` — 只读、脱敏、有界的权威 Context 视图。

## 遇错先读 Context

会话压缩、重启或工具报错后，必须先调用 `climate_read_context` 获取磁盘 Context。
磁盘 Context 是权威恢复来源。不得依赖 compact summary、对话记忆或猜测 run/step
已经成功。

## 凭证安全

禁止把 CDS 凭证、API key、token 或 `.cdsapirc` 写入工具输入、日志或 Context。
错误信息必须脱敏。

## G0～G3 范围

G0～G3 不调用 CDS，不要求真实模型。只使用离线 sample/local。workspace 外路径禁止。
本 Skill 不是通用 DAG 调度器。
