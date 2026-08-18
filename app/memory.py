from langchain_core.messages import BaseMessage

class ConversationMemory():
    def __init__(self):
        self.messages: list[BaseMessage] = []

    def add(self, message):
        self.messages.append(message)

    def get(self):
        return self.messages

    def to_dict(self):
        return {
            "messages": [
                {
                    "type": message.type,
                    "content": message.content,
                    "additional_kwargs": message.additional_kwargs,
                    "response_metadata": message.response_metadata,
                }
                for message in self.messages
            ]
        }
