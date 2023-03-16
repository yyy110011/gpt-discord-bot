from dataclasses import dataclass
from typing import Optional, List

SEPARATOR_TOKEN = "<|endoftext|>"


@dataclass(frozen=True)
class Message:
    user: str
    text: Optional[str] = None

    def render(self):
        # result = self.user + ":"
        result = {}
        result["role"] = self.user
        if self.text is not None:
            result["content"] = self.text
            # result = self.text
        return result

    # def render(self):
    #     if self.text is not None:
    #         return self.text

@dataclass
class Conversation:
    messages: List[Message]

    def prepend(self, message: Message):
        self.messages.insert(0, message)
        return self

    def render(self):
        return [message.render() for message in self.messages]


@dataclass(frozen=True)
class Config:
    name: str
    instructions: str
    example_conversations: List[Conversation]


@dataclass(frozen=True)
class Prompt:
    header: Message
    convo: Conversation

    def render(self):
        return [self.header.render()] + self.convo.render()
    
    # def render(self):
    #     return [
    #         self.header.render(),
    #         [Message("assistant", "Example conversations:").render()]
    #     ]