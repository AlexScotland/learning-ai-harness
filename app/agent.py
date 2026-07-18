import logging
from langchain_core.messages import HumanMessage, ToolMessage

logger = logging.getLogger(__name__)

class Agent:
    def __init__(self, llm, tools, memory):
        self.llm = llm
        if tools:
            self.tool_map = {
                tool.name: tool
                for tool in tools
            }
            self.llm.with_tools(tools)
        self.memory = memory

        self.max_iterations = 30  # Prevent infinite loops

    def execute_tools(self, tool_calls):
        for tool_call in tool_calls:
            try:
                tool = self.tool_map[tool_call["name"]]
                result = tool.invoke(
                    tool_call["args"]
                )
            except Exception as e:
                logger.error("Error executing tool %s: %s", tool_call["name"], str(e))
                result = f"Error executing tool {tool_call['name']}: {str(e)}"

            self.memory.add(
                ToolMessage(
                    content=str(result),
                    tool_call_id=tool_call["id"]
                )
            )

    def run(self, prompt: str):
        self.memory.add(HumanMessage(content=prompt))
        logger.debug("Running agent with messages: %s", self.memory.get())

        iteration = 0
        for iteration in range(self.max_iterations):
            logger.debug("Invoking LLM with messages: %s", self.memory.get())
            response = self.llm.invoke(self.memory.get())
            self.memory.add(response)
            if not response.tool_calls:
                return response.content

            self.execute_tools(response.tool_calls)
        return "Maximum agent iterations reached."
