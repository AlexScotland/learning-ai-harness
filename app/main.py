from agent import AgentRuntime
from inference.ollama import OllamaProvider
from memory import ConversationMemory
from tools.utils import get_current_time
from tools.summarize import list_files, read_file
from tools.memory import list_memory, search_memory, read_memory, remember
from tools.tool_registry import ToolRegistry
from state import AgentState
from planners.llm_planner import LLMPlanner
from tasks.task_executor import LLMTaskExecutor
from agent_config import AgentConfig

ALL_TOOLS = [get_current_time, list_files, read_file, list_memory, search_memory, read_memory, remember]


import logging
logging.basicConfig(level=logging.INFO)

def main(prompt):
    llm=OllamaProvider()

    planner = LLMPlanner(llm=llm)
    config = AgentConfig()
    tools_registry = ToolRegistry()
    tools_registry.register_many(ALL_TOOLS)
    conversation_memory = ConversationMemory()
    task_executor = LLMTaskExecutor(
        llm=llm,
        tool_registry=tools_registry,
        max_iterations=config.max_iterations
    )

    state = AgentState(agent_id="agent_1", goal=prompt, conversation=conversation_memory)
    logging.info("Agent state initialized: %s", state.to_dict())    
    agent = AgentRuntime(
        planner=planner,
        task_executor=task_executor,
        state=state,
        config=AgentConfig()
    )
    logging.info("Starting agent execution...")
    result = agent.run(prompt)
    logging.info("Agent execution completed. Result: %s", result)


if __name__ == "__main__":
    main("Where do I live?")
