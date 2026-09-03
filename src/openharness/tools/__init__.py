"""Built-in tool registration."""

from openharness.tools.ask_user_question_tool import AskUserQuestionTool
from openharness.tools.agent_tool import AgentTool
from openharness.tools.bash_tool import BashTool
from openharness.tools.base import BaseTool, ToolExecutionContext, ToolRegistry, ToolResult
from openharness.tools.brief_tool import BriefTool
from openharness.tools.config_tool import ConfigTool
from openharness.tools.cron_create_tool import CronCreateTool
from openharness.tools.cron_delete_tool import CronDeleteTool
from openharness.tools.cron_list_tool import CronListTool
from openharness.tools.cron_toggle_tool import CronToggleTool
from openharness.tools.enter_plan_mode_tool import EnterPlanModeTool
from openharness.tools.enter_worktree_tool import EnterWorktreeTool
from openharness.tools.exit_plan_mode_tool import ExitPlanModeTool
from openharness.tools.exit_worktree_tool import ExitWorktreeTool
from openharness.tools.file_edit_tool import FileEditTool
from openharness.tools.file_read_tool import FileReadTool
from openharness.tools.file_write_tool import FileWriteTool
from openharness.tools.glob_tool import GlobTool
from openharness.tools.grep_tool import GrepTool
from openharness.tools.image_generation_tool import ImageGenerationTool
from openharness.tools.image_to_text_tool import ImageToTextTool
from openharness.tools.list_mcp_resources_tool import ListMcpResourcesTool
from openharness.tools.lsp_tool import LspTool
from openharness.tools.mcp_auth_tool import McpAuthTool
from openharness.tools.mcp_tool import McpToolAdapter
from openharness.tools.notebook_edit_tool import NotebookEditTool
from openharness.tools.read_mcp_resource_tool import ReadMcpResourceTool
from openharness.tools.remote_trigger_tool import RemoteTriggerTool
from openharness.tools.send_message_tool import SendMessageTool
from openharness.tools.skill_tool import SkillTool
from openharness.tools.sleep_tool import SleepTool
from openharness.tools.task_create_tool import TaskCreateTool
from openharness.tools.task_get_tool import TaskGetTool
from openharness.tools.task_list_tool import TaskListTool
from openharness.tools.task_output_tool import TaskOutputTool
from openharness.tools.task_stop_tool import TaskStopTool
from openharness.tools.task_update_tool import TaskUpdateTool
from openharness.tools.team_create_tool import TeamCreateTool
from openharness.tools.team_delete_tool import TeamDeleteTool
from openharness.tools.todo_write_tool import TodoWriteTool
from openharness.tools.tool_search_tool import ToolSearchTool
from openharness.tools.web_fetch_tool import WebFetchTool
from openharness.tools.web_search_tool import WebSearchTool


def create_default_tool_registry(mcp_manager=None) -> ToolRegistry:
    """Return the default built-in tool registry."""
    registry = ToolRegistry()
    for tool in (
        BashTool(),
        AskUserQuestionTool(),
        FileReadTool(),
        FileWriteTool(),
        FileEditTool(),
        NotebookEditTool(),
        LspTool(),
        McpAuthTool(),
        GlobTool(),
        GrepTool(),
        ImageToTextTool(),
        ImageGenerationTool(),
        SkillTool(),
        ToolSearchTool(),
        WebFetchTool(),
        WebSearchTool(),
        ConfigTool(),
        BriefTool(),
        SleepTool(),
        EnterWorktreeTool(),
        ExitWorktreeTool(),
        TodoWriteTool(),
        EnterPlanModeTool(),
        ExitPlanModeTool(),
        CronCreateTool(),
        CronListTool(),
        CronDeleteTool(),
        CronToggleTool(),
        RemoteTriggerTool(),
        TaskCreateTool(),
        TaskGetTool(),
        TaskListTool(),
        TaskStopTool(),
        TaskOutputTool(),
        TaskUpdateTool(),
        AgentTool(),
        SendMessageTool(),
        TeamCreateTool(),
        TeamDeleteTool(),
    ):
        registry.register(tool)
    if mcp_manager is not None:
        registry.register(ListMcpResourcesTool(mcp_manager))
        registry.register(ReadMcpResourceTool(mcp_manager))
        for tool_info in mcp_manager.list_tools():
            registry.register(McpToolAdapter(mcp_manager, tool_info))
    _register_climate_tools(registry)
    return registry


def _register_climate_tools(registry: ToolRegistry) -> None:
    """一次性注册默认 Climate 工具（核心七工具加只读校验）；名称冲突时拒绝而不是静默覆盖。"""
    from openharness.climate.registry import create_climate_tool_registry

    for tool in create_climate_tool_registry().list_tools():
        if registry.get(tool.name) is not None:
            raise ValueError(f"工具名称已注册: {tool.name}")
        registry.register(tool)


__all__ = [
    "BaseTool",
    "ToolExecutionContext",
    "ToolRegistry",
    "ToolResult",
    "create_default_tool_registry",
]
