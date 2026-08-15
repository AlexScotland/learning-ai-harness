from agent import AgentRuntime
from inference.ollama import OllamaProvider
from memory import ConversationMemory
from tools.utils import get_current_time
from tools.summarize import list_files, read_file
from tools.memory import list_memory, search_memory, read_memory, remember
from tools.pdf import read_pdf_page, get_pdf_info
from tools.python_tools import run_python, validate_python
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
         Build a new tool for this harness at tools/wordcount.py that exposes ONE public
function:

    count_words(text: str, mode: str = "words") -> str

where mode is one of "chars", "words", "lines", "sentences". It must match the
house style of tools/pdf.py exactly: a @tool decorator, a clear docstring,
returns a readable string, and soft-fails (returns an error string, never raises)
on bad input like a non-string or an unknown mode.

If anything is broken along the way, please try too fix it.

Then verify it END-TO-END — do not skip these:
  1. Run the file through validate_python and fix any syntax/parse issues it reports.
  2. Actually execute it with run_python on at least 4 inputs:
       a) empty string ""
       b) normal prose like "The quick brown fox jumps over the lazy dog."
       c) unicode/emoji: "héllo wörld 🦄🦋"
       d) an edge case for each mode (e.g. sentences on that prose)
     Print the returned string for each.
  3. Confirm the function returns a Python str in every case (no crashes, no None).

Deliverables (both must be in your final answer):
  - The full contents of tools/wordcount.py
  - A "VERIFICATION" report: the validate_python output, then the run_python
    result block for each of the 4 inputs, with a one-line pass/fail note each.
         """)
