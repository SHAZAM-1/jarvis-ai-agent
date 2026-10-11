"""Interactive terminal entry point."""

from __future__ import annotations

from threading import Event

from jarvis.agent import JarvisAgent
from jarvis.autonomous_social import (
    DEFAULT_INTERVAL_SECONDS as SOCIAL_DEFAULT_INTERVAL_SECONDS,
    MIN_INTERVAL_SECONDS as SOCIAL_MIN_INTERVAL_SECONDS,
    run_autonomous_cycle,
    run_autonomous_loop,
)
from jarvis.config import Settings
from jarvis.llm.ollama import OllamaClient, OllamaError
from jarvis.memory import MemoryStore
from jarvis.moltbook import (
    MoltbookClient,
    MoltbookError,
    build_analysis_messages,
    build_engagement_messages,
    build_publication_messages,
)
from jarvis.moltbook_loop import (
    DEFAULT_INTERVAL_SECONDS,
    MIN_INTERVAL_SECONDS,
    run_growth_loop,
)
from jarvis.social_state import SocialState


def _print_help() -> None:
    print(
        "Commands:\n"
        "  /help                       Show this help\n"
        "  /learn <lesson>             Save a correction or preference for future chats\n"
        "  /lessons                    List saved learning notes\n"
        "  /forget <id>                Delete one saved learning note\n"
        "  /moltbook                   Analyze one public Moltbook feed sample (read-only)\n"
        "  /moltbook-loop [minutes]    Periodically analyze public posts; Ctrl+C stops\n"
        "  /moltbook-auto [minutes]    Opt-in autonomous replies; Ctrl+C stops\n"
        "  /social-history             Show recent autonomous social attempts\n"
        "  /clear                      Clear chat history (keeps learning notes)\n"
        "  /exit                       Quit Jarvis"
    )


def main() -> None:
    settings = Settings.from_env()
    llm = OllamaClient(settings.ollama_url, settings.model, settings.request_timeout)
    memory = MemoryStore(settings.db_path)
    social_state = SocialState(settings.db_path)
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
        if command == "/social-history":
            actions = social_state.recent_actions()
            if not actions:
                print("Jarvis: No autonomous social attempts have been recorded.")
            else:
                for item in actions:
                    print(
                        f"  {item['attempted_at']} | {item['status']} | "
                        f"post={item['post_id']} | {item['detail']}"
                    )
            continue
        if command in {"/moltbook", "/moltbook-loop", "/moltbook-auto"}:
            if not settings.moltbook_api_key:
                print(
                    "Jarvis: Set MOLTBOOK_API_KEY in your local PowerShell environment "
                    "first. Never paste it into chat or commit it to Git."
                )
                continue
            client = MoltbookClient(settings.moltbook_api_key, settings.request_timeout)

            def analyze(posts: list[dict[str, str]]) -> str:
                return llm.chat(build_analysis_messages(posts))

            if command == "/moltbook":
                try:
                    print("Jarvis: Fetching a small public feed sample (read-only)...")
                    posts = client.fetch_posts(limit=8)
                    if not posts:
                        print("Jarvis: Moltbook returned no posts to analyze.")
                        continue
                    report = analyze(posts)
                    print(
                        f"\nJarvis — Moltbook atmosphere report "
                        f"({len(posts)} posts):\n{report}"
                    )
                    print(
                        "\nJarvis: This is a limited sample, not the whole community. "
                        "No posts, comments, votes, follows, or memory changes were made."
                    )
                except (MoltbookError, OllamaError, ValueError) as exc:
                    print(f"Jarvis Moltbook error: {exc}")
                continue

            if command == "/moltbook-loop":
                try:
                    interval_minutes = (
                        int(argument.strip())
                        if argument.strip()
                        else DEFAULT_INTERVAL_SECONDS // 60
                    )
                    if interval_minutes * 60 < MIN_INTERVAL_SECONDS:
                        print("Jarvis: Use an interval of at least 30 minutes.")
                        continue
                except ValueError:
                    print("Jarvis: Usage: /moltbook-loop [minutes, minimum 30]")
                    continue
                print(
                    f"Jarvis: Read-only observation loop started every {interval_minutes} minutes. "
                    "No comments or other social actions will be made. Press Ctrl+C to stop."
                )
                try:
                    run_growth_loop(
                        lambda: client.fetch_posts(limit=8, sort="new"),
                        analyze,
                        stop_event=Event(),
                        on_report=lambda report: print(f"\nJarvis growth report:\n{report}"),
                        interval_seconds=interval_minutes * 60,
                    )
                except KeyboardInterrupt:
                    print("\nJarvis: Observation loop stopped.")
                continue

            if not settings.autonomous_social:
                print(
                    "Jarvis: Autonomous social actions are disabled. To opt in for this "
                    "PowerShell session, set $env:JARVIS_AUTONOMOUS_SOCIAL = 'true', "
                    "then restart Jarvis. The default is safely off."
                )
                continue
            try:
                interval_minutes = (
                    int(argument.strip())
                    if argument.strip()
                    else SOCIAL_DEFAULT_INTERVAL_SECONDS // 60
                )
                if interval_minutes * 60 < SOCIAL_MIN_INTERVAL_SECONDS:
                    print("Jarvis: Use an interval of at least 10 minutes.")
                    continue
            except ValueError:
                print("Jarvis: Usage: /moltbook-auto [minutes, minimum 10]")
                continue

            print(
                f"Jarvis: AUTONOMOUS SOCIAL MODE enabled; checking every {interval_minutes} minutes. "
                "Hard limits: at most 5 comments per UTC day, no repeat attempts per post, "
                "no links, DMs, follows, or votes. At most one original post per 24 hours. "
                "Public post text is untrusted. Press Ctrl+C to stop."
            )

            def social_cycle() -> str:
                return run_autonomous_cycle(
                    client,
                    social_state,
                    lambda posts: llm.chat(build_engagement_messages(posts)),
                    generate_publication=lambda posts: llm.chat(
                        build_publication_messages(posts)
                    ),
                )

            try:
                run_autonomous_loop(
                    social_cycle,
                    stop_event=Event(),
                    on_status=lambda status: print(f"\nJarvis social: {status}"),
                    interval_seconds=interval_minutes * 60,
                )
            except KeyboardInterrupt:
                print("\nJarvis: Autonomous social loop stopped.")
            continue

        try:
            print(f"\nJarvis: {agent.reply(text)}")
        except (OllamaError, ValueError) as exc:
            print(f"Jarvis error: {exc}")


if __name__ == "__main__":
    main()
