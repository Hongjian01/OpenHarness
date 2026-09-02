"""Climate 独立 ToolRegistry；7 工具齐备后也供默认 registry 一次性接入。"""

from __future__ import annotations

from openharness.climate.tools import (
    ClimateAcquireDataTool,
    ClimateAnalyzePlotTool,
    ClimateInitWorkflowTool,
    ClimateInspectDatasetTool,
    ClimatePlanStepsTool,
    ClimateReadContextTool,
    ClimateWriteReportTool,
)
from openharness.tools.base import BaseTool, ToolRegistry


class ClimateToolRegistry(ToolRegistry):
    """拒绝同名覆盖，避免静默替换已注册工具。"""

    def register(self, tool: BaseTool) -> None:
        if self.get(tool.name) is not None:
            raise ValueError(f"工具名称已注册: {tool.name}")
        super().register(tool)


def create_climate_tool_registry() -> ClimateToolRegistry:
    """返回仅含 7 个 Climate 工具的独立 registry。"""
    registry = ClimateToolRegistry()
    for tool in (
        ClimateInitWorkflowTool(),
        ClimatePlanStepsTool(),
        ClimateAcquireDataTool(),
        ClimateInspectDatasetTool(),
        ClimateAnalyzePlotTool(),
        ClimateWriteReportTool(),
        ClimateReadContextTool(),
    ):
        registry.register(tool)
    return registry
