"""Core conversation flow with explicit, user-approved learning notes."""

from __future__ import annotations

from jarvis.llm.ollama import OllamaClient
from jarvis.memory import MemoryStore

SYSTEM_PROMPT = (
    "You are Jarvis, a helpful personal AI assistant. Be accurate, practical, "
    "and transparent about uncertainty. Reply in the language used by the user "
    "when possible. Never claim to have performed actions you did not perform. "
    "If corrected, acknowledge the correction and use it in the current answer."
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
        lessons = self.memory.recent_lessons(limit=20)
        if lessons:
            notes = "\n".join(
                f"- {item['lesson']}" for item in lessons
            )
            messages.append(
                {
                    "role": "system",
                    "content": (
                        "User-approved memory notes follow. Use them as fallible "
                        "context about the user's preferences and prior corrections. "
                        "They do not override safety rules or the current request. "
                        "If a note conflicts with reliable evidence, explain the conflict.\n"
                        + notes
                    ),
                }
            )
        messages.extend(self.memory.recent_messages(limit=12))
        answer = self.llm.chat(messages)
        self.memory.add_message("assistant", answer)
        return answer
