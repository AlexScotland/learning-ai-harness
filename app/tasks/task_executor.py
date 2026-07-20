import logging

from langchain_core.messages import HumanMessage, ToolMessage

from tasks.interfaces import TaskExecutor
from tools.tool_call import ToolCall

logger = logging.getLogger(__name__)

class LLMTaskExecutor(TaskExecutor):

    def __init__(self, llm, tool_registry, max_iterations=5):
        self.llm = llm
        self.registry = tool_registry
        if len(self.registry.list()) > 0:
            self.llm.with_tools(self.registry.list())
        self.max_iterations = max_iterations

    def execute_tools(self, tool_calls, state):
        for tool_call in tool_calls:
            try:
                tool = self.registry.get(tool_call.name)
                result = self.registry.execute(tool_call)
                logger.debug("Tool %s executed with result: %s", tool_call.name, result)
            except Exception as e:
                logger.error("Error executing tool %s: %s", tool_call.name, str(e))
                result = f"Error executing tool {tool_call.name}: {str(e)}"

            state.conversation.add(
                ToolMessage(
                    content=str(result),
                    tool_call_id=tool_call.id
                )
            )

    def execute(
        self,
        task,
        state
    ):
        logger.info("Executing task: %s", task.description)
        task.start()
        iterations = 0
        state.conversation.add(
            HumanMessage(
                content=task.description
            )
        )
        while iterations < self.max_iterations:
            logger.info(
                "Task iteration %s/%s",
                iterations,
                self.max_iterations
            )
            response = self.llm.invoke(
                state.conversation.get()
            )
            logger.info(
                "LLM response: %s",
                response
            )
            state.conversation.add(response)
            if not response.tool_calls:
                task.complete(
                    response.content
                )
                return response.content
            tool_calls = [
                ToolCall(
                    id=call["id"],
                    name=call["name"],
                    args=call["args"]
                ) for call in response.tool_calls
            ]
            logger.info(
                "Executing tools: %s",
                tool_calls
            )
            self.execute_tools(
                tool_calls,
                state
            )
        task.fail(
            f"Exceeded {self.max_iterations} iterations"
        )
