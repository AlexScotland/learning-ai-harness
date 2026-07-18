from langchain_core.messages import BaseMessage

class ConversationMemory():
    def __init__(self):
        self.messages: list[BaseMessage] = []

    def add(self, message):
        self.messages.append(message)

    def get(self):
        return self.messages