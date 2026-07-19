from agent import Agent
from inference.ollama import OllamaProvider
from memory import ConversationMemory
from tools.utils import get_current_time
from tools.summarize import list_files, read_file
from tools.memory import list_memory, search_memory, read_memory, remember



import logging
SYSTEM_PROMPT = "You are a helpful assistant"
logging.basicConfig(level=logging.DEBUG)

def main():
    memory = ConversationMemory()
    agent = Agent(
        llm=OllamaProvider(),
        memory=memory,
        tools=[get_current_time, list_files, read_file, list_memory, search_memory, read_memory, remember]
    )
    print(agent.run("Where do i live?"))
if __name__ == "__main__":
    main()
