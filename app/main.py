from agent import AgentRuntime
from inference.ollama import OllamaProvider
from memory import ConversationMemory
from tools.utils import get_current_time
from tools.summarize import list_files, read_file
from tools.memory import list_memory, search_memory, read_memory, remember
from tools.pdf import read_pdf_page, get_pdf_info
from tools.tool_registry import ToolRegistry
from state import AgentState
from planners.llm_planner import LLMPlanner
from tasks.task_executor import LLMTaskExecutor
from evaluator import TaskEvaluator
from agent_config import AgentConfig
from goals import Goal, GoalExtractor


ALL_TOOLS = [get_pdf_info, read_pdf_page, list_files,
             read_file, search_memory, read_memory, remember, list_memory]


import logging
logging.basicConfig(level=logging.INFO)


def main(prompt):
    llm=OllamaProvider(
        model="Duggles/qwen-3-8-larger-context:latest"
    )
    # One extractor, one Goal. No router, no factory, no per-type registration.
    goal_extractor = GoalExtractor(llm=llm)

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
    goal = goal_extractor.extract(prompt)
    # goal = GoalExtractor(llm=llm).extract_goal_data(prompt)
    state = AgentState(agent_id="agent_1", goal=goal, conversation=conversation_memory)
    logging.info("Agent state initialized: %s", state.to_dict())    
    agent = AgentRuntime(
        planner=planner,
        task_executor=task_executor,
        evaluator=TaskEvaluator(),
        state=state,
        config=AgentConfig()
    )
    logging.info("Starting agent execution...")
    result = agent.run()
    logging.info("Agent execution completed. Result: %s", result)


if __name__ == "__main__":
    main("""
         DO NOT WRITE ANY CODE!
        I want to make you a new tool! It will be a tool to let you validate, generate and run python code!  Looking at the architecture of the /app/ directory - what do you suggest we do for these tools?
         """)
