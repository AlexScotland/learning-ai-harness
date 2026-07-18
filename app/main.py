from langchain_core.messages import HumanMessage, SystemMessage

from agent import Agent
from inference.ollama import OllamaProvider
from memory import ConversationMemory
from tools.utils import get_current_time
from tools.summarize import list_files, read_file



import logging
SYSTEM_PROMPT = "You are a helpful assistant"
logging.basicConfig(level=logging.INFO)

def main():
    memory = ConversationMemory()
    memory.add(SystemMessage(content=SYSTEM_PROMPT))
    agent = Agent(
        llm=OllamaProvider(),
        memory=memory,
        tools=[get_current_time, list_files, read_file]
    )
    print(agent.run("What is the current time?"))
if __name__ == "__main__":
    main()
