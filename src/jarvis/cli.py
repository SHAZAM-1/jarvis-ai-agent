"""Interactive terminal entry point."""

from __future__ import annotations

from jarvis.agent import JarvisAgent
from jarvis.config import Settings
from jarvis.llm.ollama import OllamaClient, OllamaError
from jarvis.memory import MemoryStore


def main() -> None:
    settings = Settings.from_env()
    llm = OllamaClient(settings.ollama_url, settings.model, settings.request_timeout)
    memory = MemoryStore(settings.db_path)
    agent = JarvisAgent(llm, memory)

    print("Jarvis AI Agent — local mode")
    print(f"Model: {settings.model}")
    print("Type /help for commands, /exit to quit. Your conversation is saved locally.")
    if not llm.is_available():
        print("WARNING: Ollama is not responding. Start Ollama, then try again.")
    while True:
        try:
            text = input("\nYou: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nJarvis: Goodbye.")
            break
        if not text:
            continue
        if text.lower() in {"/exit", "/quit"}:
            print("Jarvis: Goodbye.")
            break
        if text.lower() == "/help":
            print("Commands: /help, /clear, /exit")
            continue
        if text.lower() == "/clear":
            memory.clear()
            print("Jarvis: Local conversation memory cleared.")
            continue
        try:
            print(f"\nJarvis: {agent.reply(text)}")
        except (OllamaError, ValueError) as exc:
            print(f"Jarvis error: {exc}")


if __name__ == "__main__":
    main()
