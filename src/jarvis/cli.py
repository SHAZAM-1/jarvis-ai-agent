"""Interactive terminal entry point."""

from __future__ import annotations

from jarvis.agent import JarvisAgent
from jarvis.config import Settings
from jarvis.llm.ollama import OllamaClient, OllamaError
from jarvis.memory import MemoryStore
from jarvis.moltbook import MoltbookClient, MoltbookError, build_analysis_messages


def _print_help() -> None:
    print(
        "Commands:\n"
        "  /help                 Show this help\n"
        "  /learn <lesson>       Save a correction or preference for future chats\n"
        "  /lessons              List saved learning notes\n"
        "  /forget <id>          Delete one saved learning note\n"
        "  /moltbook             Analyze a small public Moltbook feed sample (read-only)\n"
        "  /clear                Clear chat history (keeps learning notes)\n"
        "  /exit                 Quit Jarvis"
    )


def main() -> None:
    settings = Settings.from_env()
    llm = OllamaClient(settings.ollama_url, settings.model, settings.request_timeout)
    memory = MemoryStore(settings.db_path)
    agent = JarvisAgent(llm, memory)

    print("Jarvis AI Agent — local mode")
    print(f"Model: {settings.model}")
    print("Type /help for commands, /exit to quit. Data is saved locally.")
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

        command, _, argument = text.partition(" ")
        command = command.lower()
        if command in {"/exit", "/quit"}:
            print("Jarvis: Goodbye.")
            break
        if command == "/help":
            _print_help()
            continue
        if command == "/clear":
            memory.clear()
            print("Jarvis: Chat history cleared. Learning notes are preserved.")
            continue
        if command == "/learn":
            try:
                lesson_id = memory.add_lesson(argument)
                print(
                    f"Jarvis: Saved learning note #{lesson_id}. "
                    "I'll use it as context in future replies."
                )
            except ValueError as exc:
                print(f"Jarvis: {exc}. Usage: /learn <correction or preference>")
            continue
        if command == "/lessons":
            lessons = memory.recent_lessons()
            if not lessons:
                print("Jarvis: No learning notes saved yet. Use /learn <lesson>.")
            else:
                print("Jarvis: Saved learning notes:")
                for item in lessons:
                    print(f"  #{item['id']} [{item['created_at']}] {item['lesson']}")
            continue
        if command == "/forget":
            try:
                lesson_id = int(argument.strip())
                removed = memory.delete_lesson(lesson_id)
                print(
                    f"Jarvis: Learning note #{lesson_id} deleted."
                    if removed
                    else f"Jarvis: No learning note found with ID #{lesson_id}."
                )
            except (ValueError, TypeError):
                print("Jarvis: Usage: /forget <numeric lesson ID>")
            continue
        if command == "/moltbook":
            if not settings.moltbook_api_key:
                print(
                    "Jarvis: Set MOLTBOOK_API_KEY in your local PowerShell environment "
                    "first. Never paste it into chat or commit it to Git."
                )
                continue
            try:
                print("Jarvis: Fetching a small public feed sample (read-only)...")
                posts = MoltbookClient(settings.moltbook_api_key).fetch_posts(limit=8)
                if not posts:
                    print("Jarvis: Moltbook returned no posts to analyze.")
                    continue
                report = llm.chat(build_analysis_messages(posts))
                print(f"\nJarvis — Moltbook atmosphere report ({len(posts)} posts):\n{report}")
                print(
                    "\nJarvis: This is a limited sample, not the whole community. "
                    "No posts, comments, votes, follows, or memory changes were made."
                )
            except (MoltbookError, OllamaError, ValueError) as exc:
                print(f"Jarvis Moltbook error: {exc}")
            continue

        try:
            print(f"\nJarvis: {agent.reply(text)}")
        except (OllamaError, ValueError) as exc:
            print(f"Jarvis error: {exc}")


if __name__ == "__main__":
    main()
