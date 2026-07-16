import logging
logger = logging.getLogger(__name__)

class Agent:
    def __init__(self, llm, tools, system_prompt="You are a helpful assistant."):
        self.llm = llm
        if tools:
            self.tool_map = {
                tool.name: tool
                for tool in tools
            }
            self.llm.with_tools(tools)
        self.system_prompt = system_prompt

        self.max_iterations = 30  # Prevent infinite loops

    def run(self, prompt):
        logger.debug("Running agent with prompt: %s", prompt)
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": prompt}
        ]
        iteration = 0
        while iteration < self.max_iterations:
            logger.debug("Invoking LLM with messages: %s", messages)
            response = self.llm.invoke(messages)
            if response.tool_calls:
                logger.debug("Tool calls detected: %s", response.tool_calls)
                for tool_call in response.tool_calls:
                    logger.debug("Invoking tool: %s with args: %s", tool_call["name"], tool_call["args"])
                    tool = self.tool_map[tool_call["name"]]

                    result = tool.invoke(
                        tool_call["args"]
                    )
                    logger.debug("Tool result: %s", result)

                    messages.append(
                        {
                            "role": "tool",
                            "content": result,
                            "tool_call_id": tool_call["id"]
                        }
                    )

            else:
                logger.debug("Final response: %s", response.content)
                print(response.content)
                break
            iteration += 1