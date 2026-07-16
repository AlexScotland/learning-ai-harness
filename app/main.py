from agent import Agent
from inference.ollama import OllamaProvider
from tools.utils import get_current_time
from tools.summarize import list_files, read_file

import logging

logging.basicConfig(level=logging.DEBUG)


agent = Agent(
    llm=OllamaProvider(),
    tools=[get_current_time, list_files, read_file]
)
agent_response = agent.run("Summarize the files in the current directory and subdirectories")
print(agent_response)