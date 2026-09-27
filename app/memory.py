from langchain_core.messages import BaseMessage

class ConversationMemory():
    def __init__(self):
        self.messages: list[BaseMessage] = []

    def add(self, message):
        self.messages.append(message)

    def replace(self, messages: list[BaseMessage]):
        """Replace the entire conversation with a new set of messages.

        Used in stateless (HTTP) mode: each request supplies the conversation
        itself, so the server never carries turns over on its own.
        """
        self.messages = list(messages)

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
