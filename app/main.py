from agent import Agent
from inference.ollama import OllamaProvider
from memory import ConversationMemory
from tools.utils import get_current_time
from tools.summarize import list_files, read_file
from tools.memory import list_memory, search_memory, read_memory, remember
from state import AgentState
from planners.llm_planner import LLMPlanner



import logging
SYSTEM_PROMPT = "You are a helpful assistant"
logging.basicConfig(level=logging.INFO)

def main(prompt):
    llm=OllamaProvider()
    planner = LLMPlanner(llm=llm)
    conversation_memory = ConversationMemory()
    state = AgentState(agent_id="agent_1", goal=prompt, conversation=conversation_memory)
    logging.info("Agent state initialized: %s", state.to_dict())
    tasks = planner.create_plan(state)
    logging.info("Generated plan: %s", tasks)
    agent = Agent(
        llm=llm,
        state=state,
        tools=[get_current_time, list_files, read_file, list_memory, search_memory, read_memory, remember]
    )
    logging.info("Starting agent execution...")
    result = agent.run(prompt)
    logging.info("Agent execution completed. Result: %s", result)


if __name__ == "__main__":
    main("Please remember that I live in Hamilton Ontario")
