import logging
from langchain_core.messages import HumanMessage, ToolMessage, SystemMessage

logger = logging.getLogger(__name__)

class Agent:
    def __init__(self, llm, tools, state, agent_path="AGENTS.md"):
        self.llm = llm
        self.state = state
        if tools:
            self.tool_map = {
                tool.name: tool
                for tool in tools
            }
            self.llm.with_tools(tools)
        self.state.conversation.add(SystemMessage(content=self.load_agent_instructions(agent_path)))
        self.max_iterations = 30  # Prevent infinite loops

    def load_agent_instructions(self, path):
        with open(path) as f:
            return f.read()

    def execute_tools(self, tool_calls):
        for tool_call in tool_calls:
            try:
                tool = self.tool_map[tool_call["name"]]
                result = tool.invoke(
                    tool_call["args"]
                )
                logger.debug("Tool %s executed with result: %s", tool_call["name"], result)
            except Exception as e:
                logger.error("Error executing tool %s: %s", tool_call["name"], str(e))
                result = f"Error executing tool {tool_call['name']}: {str(e)}"

            self.state.conversation.add(
                ToolMessage(
                    content=str(result),
                    tool_call_id=tool_call["id"]
                )
            )

    def run(self, prompt: str):
        self.state.conversation.add(HumanMessage(content=prompt))
        logger.debug("Running agent with messages: %s", self.state.conversation.get())

        iteration = 0
        for iteration in range(self.max_iterations):
            logger.debug("Invoking LLM with messages: %s", self.state.conversation.get())
            response = self.llm.invoke(self.state.conversation.get())
            self.state.conversation.add(response)
            if not response.tool_calls:
                return response.content

            self.execute_tools(response.tool_calls)
        return "Maximum agent iterations reached."
