from langchain_core.tools import BaseTool
from tools.tool_call import ToolCall


class ToolRegistry:

    def __init__(self):
        self._tools: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool):
        self._tools[tool.name] = tool

    def register_many(self, tools: list[BaseTool]):
        for tool in tools:
            self.register(tool)

    def get(self, name: str) -> BaseTool | None:
        return self._tools.get(name)

    def execute(self, tool_call: ToolCall):
        tool = self.get(tool_call.name)

        if tool is None:
            raise ValueError(
                f"Unknown tool: {tool_call.name}"
            )

        return tool.invoke(
            tool_call.args
        )

    def list(self):
        return list(self._tools.values())

    def names(self):
        return list(self._tools.keys())