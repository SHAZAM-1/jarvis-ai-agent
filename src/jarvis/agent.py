"""Core conversation flow; tools and planning are intentionally not enabled yet."""

from __future__ import annotations

from jarvis.llm.ollama import OllamaClient
from jarvis.memory import MemoryStore

SYSTEM_PROMPT = (
    "You are Jarvis, a helpful personal AI assistant. Be accurate, practical, "
    "and transparent about uncertainty. Reply in the language used by the user "
    "when possible. Never claim to have performed actions you did not perform."
)


class JarvisAgent:
    def __init__(self, llm: OllamaClient, memory: MemoryStore) -> None:
        self.llm = llm
        self.memory = memory

    def reply(self, user_text: str) -> str:
        text = user_text.strip()
        if not text:
            raise ValueError("Please enter a message.")
        self.memory.add_message("user", text)
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        messages.extend(self.memory.recent_messages(limit=12))
        answer = self.llm.chat(messages)
        self.memory.add_message("assistant", answer)
        return answer
