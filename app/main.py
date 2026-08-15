from agent import AgentRuntime
from inference.ollama import OllamaProvider
from memory import ConversationMemory
from tools.utils import get_current_time
from tools.summarize import list_files, read_file
from tools.memory import list_memory, search_memory, read_memory, remember
from tools.pdf import read_pdf_page, get_pdf_info
from tools.python_tools import validate_python, run_python
from tools.files import write_file
from tools.tool_registry import ToolRegistry
from state import AgentState
from planners.llm_planner import LLMPlanner
from tasks.task_executor import LLMTaskExecutor
from evaluator import TaskEvaluator
from agent_config import AgentConfig
from goals import Goal, GoalExtractor

ALL_TOOLS = [get_pdf_info, read_pdf_page, list_files, read_file,
             list_memory, search_memory, read_memory, remember,
             validate_python, run_python, write_file]


import logging
logging.basicConfig(level=logging.INFO)

BANNER = (
    "========================================\n"
    "  Interactive Agent Conversation\n"
    "  Ask questions and get answers from the agent.\n"
    "  Type 'exit' or 'quit' (or press Ctrl-D) to end the session.\n"
    "========================================"
)


def build_agent():
    """Construct a fully-wired agent that shares one ConversationMemory,
    so every turn of the conversation builds on the previous ones."""
    llm = OllamaProvider(model="Duggles/qwen-3-8-larger-context:latest")

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
    state = AgentState(agent_id="agent_1", goal=None, conversation=conversation_memory)
    logging.info("Agent state initialized: %s", state.to_dict())

    agent = AgentRuntime(
        planner=planner,
        task_executor=task_executor,
        evaluator=TaskEvaluator(),
        state=state,
        config=AgentConfig(),
        goal_extractor=goal_extractor,
    )
    return agent


def main():
    """Launch an interactive, multi-turn conversation with the agent.

    The user asks questions at the prompt; the agent answers each one.
    The loop keeps running until the user exits, so the whole session is a
    full conversation rather than a single Q&A. No code changes are needed
    to ask questions or receive answers.
    """
    agent = build_agent()
    print(BANNER)

    while True:
        try:
            user_input = input("\nYou> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye.")
            break

        if not user_input:
            continue
        if user_input.lower() in ("exit", "quit", "q", "bye"):
            print("Goodbye.")
            break

        try:
            answer = agent.chat(user_input)
        except Exception as exc:  # keep the session alive on a bad turn
            logging.exception("Agent turn failed")
            print(f"Agent> (error) {exc}")
            continue

        print(f"\nAgent> {answer}")


if __name__ == "__main__":
    main()
