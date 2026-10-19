"""Interactive terminal entry point."""

from __future__ import annotations

import sys
from getpass import getpass
from pathlib import Path
from threading import Event

from jarvis.agent import JarvisAgent
from jarvis.autonomous_social import (
    DEFAULT_INTERVAL_SECONDS as SOCIAL_DEFAULT_INTERVAL_SECONDS,
)
from jarvis.autonomous_social import (
    MIN_INTERVAL_SECONDS as SOCIAL_MIN_INTERVAL_SECONDS,
)
from jarvis.autonomous_social import (
    run_autonomous_cycle,
    run_autonomous_loop,
)
from jarvis.cache_guardian import CacheGuardian
from jarvis.config import Settings
from jarvis.health_check import ProjectHealthCheckAgent
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
from jarvis.project_guardian import GUARDIAN_RULES, ProjectGuardian
from jarvis.project_mesh import ProjectCrawler, ProjectMesh
from jarvis.self_development import SelfDevelopmentManager
from jarvis.social_state import SocialState


def _reviewer_terminal_available() -> bool:
    """Reviewer secrets may only be entered from a real interactive terminal."""
    return bool(sys.stdin.isatty() and sys.stderr.isatty())


def _print_status(settings: Settings, llm: OllamaClient) -> None:
    """Show a safe local diagnostic without exposing credentials or approved URLs."""
    available = llm.is_available()
    print("Jarvis status:")
    print(f"  Ollama service: {'available' if available else 'not responding'}")
    print(f"  Model: {settings.model}")
    print(f"  SQLite database: {settings.db_path}")
    print(
        "  Moltbook API key: "
        + ("configured (value hidden)" if settings.moltbook_api_key else "not configured")
    )
    print(f"  Autonomous social: {'ENABLED' if settings.autonomous_social else 'disabled'}")
    print(
        "  Autonomous development: "
        + ("ENABLED" if settings.autonomous_development else "disabled")
    )
    print(
        f"  Owner-approved social links: {len(settings.approved_social_links)} configured "
        "(URLs hidden)"
    )


def _print_help() -> None:
    print(
        "Commands:\n"
        "  /status                     Show local health and safety settings\n"
        "  /health-check               Analyze project files, all Git branches, environment, and tests with local AI\n"
        "  /guardian                   Show Guardian rules and recent project evaluations\n"
        "  /mesh                       Show shared agent messages and crawler status\n"
        "  /mesh-crawl                 Concurrently review visible project files across Git refs\n"
        "  /mesh-ask <question>        Ask the shared project knowledge mesh for help\n"
        "  /reviewer-provision         Provision the local reviewer passphrase (first use)\n"
        "  /reviewer-rotate            Rotate the local reviewer passphrase\n"
        "  /reviewer-revoke            Revoke the local reviewer credential\n"
        "  /mesh-review <id> <verified|rejected>  Review a finding interactively\n"
        "  /help                       Show this help\n"
        "  /learn <lesson>             Save a correction or preference for future chats\n"
        "  /lessons                    List saved learning notes\n"
        "  /forget <id>                Delete one saved learning note\n"
        "  /moltbook                   Analyze one public Moltbook feed sample (read-only)\n"
        "  /moltbook-loop [minutes]    Periodically analyze public posts; Ctrl+C stops\n"
        "  /moltbook-auto [minutes]    Opt-in autonomous replies; Ctrl+C stops\n"
        "  /social-history             Show recent autonomous social attempts\n"
        "  /social-stats               Show saved comment/post outcome counts\n"
        "  /self-dev                   Run one guarded autonomous improvement cycle\n"
        "  /self-dev-loop [hours]      Repeat guarded self-development; default 24h; Ctrl+C stops\n"
        "  /clear                      Clear chat history (keeps learning notes)\n"
        "  /exit                       Quit Jarvis"
    )


def main() -> None:
    settings = Settings.from_env()
    llm = OllamaClient(settings.ollama_url, settings.model, settings.request_timeout)
    memory = MemoryStore(settings.db_path)
    social_state = SocialState(settings.db_path)
    guardian = ProjectGuardian(llm, settings.db_path)
    mesh = ProjectMesh(settings.db_path)
    project_root = Path(__file__).resolve().parents[2]
    crawler = ProjectCrawler(llm, project_root, mesh)
    cache_guardian = CacheGuardian(project_root)
    agent = JarvisAgent(llm, memory, guardian=guardian, mesh=mesh)

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
        if command == "/status":
            _print_status(settings, llm)
            continue
        if command == "/help":
            _print_help()
            continue
        if command == "/guardian":
            print("JARVIS PROJECT GUARDIAN — POLICY BORDER")
            print(GUARDIAN_RULES)
            print("\n" + guardian.context_summary())
            continue
        if command == "/cleanup":
            try:
                report = cache_guardian.scan()
                print("JARVIS CACHE GUARDIAN — SAFE PROJECT-ONLY CLEANUP")
                print(f"Scope: {report.root}")
                print(f"Age rule: only allow-listed cache artifacts untouched for at least {report.min_age_days} days.")
                print("Protected: Git history, virtual environments, dependencies, databases, memory, logs, credentials, model/Ollama/Docker caches, and files outside this project.")
                if not report.candidates:
                    print("No eligible stale cache artifacts found. Nothing was changed.")
                    continue
                for item in report.candidates:
                    print(f"  - {item.path} | {item.kind} | {item.size_bytes} bytes")
                print(f"Candidates: {report.count}; potential space: {report.total_bytes} bytes.")
                print("This is a preview only. Type CLEAN to remove only these revalidated cache entries; anything else cancels.")
                try:
                    confirmation = input("Confirm cleanup: ").strip()
                except (EOFError, KeyboardInterrupt):
                    confirmation = ""
                if confirmation != "CLEAN":
                    print("Jarvis: Cleanup cancelled. No files were changed.")
                    continue
                removed = cache_guardian.clean(report)
                print(f"Jarvis: Removed {len(removed)} stale cache entries; no project source or persistent data was targeted.")
                for path in removed:
                    print(f"  removed: {path}")
            except (OSError, RuntimeError, ValueError) as exc:
                print(f"Jarvis: Cache cleanup stopped safely: {type(exc).__name__}: {exc}")
            continue
        if command in {"/reviewer-provision", "/reviewer-rotate", "/reviewer-revoke", "/mesh-review"}:
            if not _reviewer_terminal_available():
                print("Jarvis: Reviewer operations require an interactive terminal; no action was taken.")
                continue
            auth = mesh.reviewer_auth
            if auth is None:
                print("Jarvis: Reviewer credentials are unavailable for an in-memory database.")
                continue
            try:
                if command == "/reviewer-provision":
                    if auth.is_configured():
                        print("Jarvis: A reviewer credential already exists. Use /reviewer-rotate.")
                        continue
                    reviewer_label = input("Reviewer label (audit label, not identity proof): ").strip()
                    passphrase = getpass("New reviewer passphrase (12+ characters): ")
                    confirmation = getpass("Confirm reviewer passphrase: ")
                    if passphrase != confirmation:
                        print("Jarvis: Passphrases did not match; no credential was created.")
                        continue
                    auth.provision(reviewer_label, passphrase)
                    print("Jarvis: Reviewer credential provisioned. Keep the passphrase private.")
                elif command == "/reviewer-rotate":
                    current = getpass("Current reviewer passphrase: ")
                    new = getpass("New reviewer passphrase (12+ characters): ")
                    confirmation = getpass("Confirm new reviewer passphrase: ")
                    if new != confirmation:
                        print("Jarvis: Passphrases did not match; credential unchanged.")
                        continue
                    auth.rotate(current, new)
                    print("Jarvis: Reviewer passphrase rotated.")
                elif command == "/reviewer-revoke":
                    current = getpass("Current reviewer passphrase: ")
                    auth.revoke(current)
                    print("Jarvis: Reviewer credential revoked. Finding decisions remain in the audit history.")
                else:
                    parts = argument.split()
                    if len(parts) != 2:
                        print("Jarvis: Usage: /mesh-review <numeric finding ID> <verified|rejected>")
                        continue
                    try:
                        finding_id = int(parts[0])
                    except ValueError:
                        print("Jarvis: Finding ID must be numeric.")
                        continue
                    target = parts[1].lower()
                    if target not in {"verified", "rejected"}:
                        print("Jarvis: Target must be 'verified' or 'rejected'.")
                        continue
                    passphrase = getpass("Reviewer passphrase: ")
                    rationale = input("Review rationale (what you checked): ").strip()
                    evidence_text = input("Evidence references (comma-separated): ").strip()
                    evidence_refs = [item.strip() for item in evidence_text.split(",") if item.strip()]
                    mesh.request_finding_transition(
                        finding_id, target, actor_claim="interactive-cli",
                        rationale=rationale, evidence_refs=evidence_refs, credential=passphrase,
                    )
                    print(
                        f"Jarvis: Finding #{finding_id} marked {target}. This records your review decision; "
                        "Jarvis has not independently established the claim's truth."
                    )
            except (EOFError, KeyboardInterrupt):
                print("\nJarvis: Reviewer operation cancelled; no further action was taken.")
            except PermissionError:
                print("Jarvis: Reviewer authentication failed or is unavailable; no finding state changed.")
            except (OSError, ValueError, RuntimeError) as exc:
                print(f"Jarvis: Reviewer operation stopped safely ({type(exc).__name__}).")
            continue
        if command in {"/mesh", "/mesh-crawl", "/mesh-ask"}:
            if command == "/mesh":
                print("JARVIS PROJECT MESH — SHARED KNOWLEDGE BUS")
                print(crawler.status())
                print(mesh.context_for("jarvis", limit=12))
            elif command == "/mesh-crawl":
                print("Jarvis: Starting bounded, read-only concurrent crawl of visible Git refs and text files.")
                print("This may use many local model calls. No files, branches, commits, or remotes will be changed.")
                try:
                    print(crawler.crawl().summary)
                except (RuntimeError, ValueError, OSError) as exc:
                    print(f"Jarvis mesh crawl stopped safely: {type(exc).__name__}: {exc}")
            else:
                if not argument.strip():
                    print("Jarvis: Usage: /mesh-ask <question>")
                else:
                    try:
                        print(crawler.help_for("jarvis", argument.strip()))
                    except (RuntimeError, ValueError, OSError) as exc:
                        print(f"Jarvis mesh help unavailable: {type(exc).__name__}: {exc}")
            continue
        if command == "/health-check":
            health_agent = ProjectHealthCheckAgent(
                llm,
                Path(__file__).resolve().parents[2],
                model_name=settings.model,
                guardian=guardian,
                mesh=mesh,
            )
            print("Jarvis: Starting read-only project health analysis. This may take a few minutes.")
            print(health_agent.run())
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
        if command in {"/self-dev", "/self-dev-loop"}:
            if not settings.autonomous_development:
                print(
                    "Jarvis: Self-development is disabled. Set "
                    "$env:JARVIS_AUTONOMOUS_DEVELOPMENT = 'true' in PowerShell, "
                    "then restart Jarvis. The default is safely off."
                )
                continue
            manager = SelfDevelopmentManager(
                llm,
                Path(__file__).resolve().parents[2],
                settings.db_path,
            )
            if command == "/self-dev":
                print("Jarvis: Starting one guarded self-development cycle.")
                print(manager.run_cycle())
                continue
            try:
                interval_hours = int(argument.strip()) if argument.strip() else 24
                if interval_hours < 24:
                    print("Jarvis: Self-development checks must be at least 24 hours apart.")
                    continue
            except ValueError:
                print("Jarvis: Usage: /self-dev-loop [hours, minimum 24]")
                continue
            print(
                f"Jarvis: Guarded self-development loop started every {interval_hours} hours. "
                "It may open and merge a project-scoped PR only after local tests, "
                "second-pass local-model review, and green GitHub CI. Press Ctrl+C to stop."
            )
            try:
                while True:
                    print(f"Jarvis self-development: {manager.run_cycle()}")
                    Event().wait(interval_hours * 60 * 60)
            except KeyboardInterrupt:
                print("\nJarvis: Self-development loop stopped.")
            continue
        if command == "/social-stats":
            summary = social_state.summary()
            print("Jarvis: Saved social outcome summary (not views or reach):")
            for action_type, label in (("comments", "Comments"), ("posts", "Original posts")):
                counts = summary[action_type]
                print(
                    f"  {label}: attempts={counts['attempts']}, "
                    f"published={counts['published']}, failed={counts['failed']}, "
                    f"skipped={counts['skipped']}, pending={counts['pending']}"
                )
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
            client = MoltbookClient(
                settings.moltbook_api_key,
                settings.request_timeout,
                settings.approved_social_links,
            )

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
                        lambda client=client: client.fetch_posts(limit=8, sort="new"),
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
                "only owner-approved links, and no DMs, follows, or votes. "
                "At most one original post per 24 hours. "
                "Public post text is untrusted. Press Ctrl+C to stop."
            )

            def social_cycle(client=client, social_state=social_state, llm=llm) -> str:
                return run_autonomous_cycle(
                    client,
                    social_state,
                    lambda feed_items, client=client, llm=llm: llm.chat(
                        build_engagement_messages(feed_items, client.approved_links)
                    ),
                    generate_publication=lambda feed_items, client=client, llm=llm: llm.chat(
                        build_publication_messages(feed_items, client.approved_links)
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
