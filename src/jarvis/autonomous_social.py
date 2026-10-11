"""Guarded autonomous social engagement using only bounded local-model decisions."""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from threading import Event

from jarvis.moltbook import (
    MAX_COMMENT_LENGTH,
    MAX_POSTS,
    MoltbookClient,
    build_engagement_messages,
)
from jarvis.social_state import SocialState

MIN_INTERVAL_SECONDS = 30 * 60
DEFAULT_INTERVAL_SECONDS = 60 * 60
MAX_COMMENTS_PER_UTC_DAY = 1
_URL_RE = re.compile(r"https?://|www\.", re.IGNORECASE)
_CREDENTIAL_RE = re.compile(
    r"\b(password|api[ -]?key|secret|seed phrase|private key|token)\b",
    re.IGNORECASE,
)
_GENERIC_REPLIES = {
    "great post",
    "great point",
    "thanks for sharing",
    "interesting",
    "i completely agree",
}


def parse_engagement_decision(raw: str, posts: list[dict[str, str]]) -> dict[str, str] | None:
    """Validate the local model's JSON against the current feed; invalid means skip."""
    try:
        decision = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return None
    if not isinstance(decision, dict):
        return None
    action = decision.get("action")
    post_id = decision.get("post_id")
    content = decision.get("content")
    if action == "skip":
        return {"action": "skip", "post_id": "", "content": ""}
    if action != "comment" or not isinstance(post_id, str) or not isinstance(content, str):
        return None
    matching = next((post for post in posts if post.get("id") == post_id), None)
    if matching is None or not post_id:
        return None
    cleaned = content.strip()
    if not 40 <= len(cleaned) <= MAX_COMMENT_LENGTH:
        return None
    if _URL_RE.search(cleaned) or _CREDENTIAL_RE.search(cleaned):
        return None
    if cleaned.casefold().strip(" .!?") in _GENERIC_REPLIES:
        return None
    # Don't engage with empty/low-context posts; the comment must refer to actual content.
    context = f"{matching.get('title', '')} {matching.get('content', '')}".strip()
    if len(context) < 20:
        return None
    return {"action": "comment", "post_id": post_id, "content": cleaned}


def run_autonomous_cycle(
    client: MoltbookClient,
    state: SocialState,
    generate: Callable[[list[dict[str, str]]], str],
    *,
    on_status: Callable[[str], None] = print,
) -> str:
    """Fetch, decide, validate and at most attempt one comment for this cycle."""
    posts = client.fetch_posts(limit=MAX_POSTS, sort="new")
    if not posts:
        return "No public posts returned; no action taken."
    raw = generate(posts)
    decision = parse_engagement_decision(raw, posts)
    if decision is None:
        return "Model decision failed validation; no action taken."
    if decision["action"] == "skip":
        return "No post clearly merited a reply; skipped."
    post_id = decision["post_id"]
    if not state.reserve_comment(post_id, daily_limit=MAX_COMMENTS_PER_UTC_DAY):
        return "Daily comment limit reached or post already attempted; skipped."
    try:
        client.create_comment(post_id, decision["content"])
    except Exception as exc:
        state.record_outcome(post_id, "failed", type(exc).__name__)
        # Never dump exception text, which may contain external response details.
        on_status(f"Comment attempt failed safely ({type(exc).__name__}); it counts toward today's cap.")
        return "Comment attempt failed; no automatic retry."
    state.record_outcome(post_id, "published", "API accepted comment request")
    return f"Comment submitted on post {post_id}."


def run_autonomous_loop(
    cycle: Callable[[], str],
    *,
    stop_event: Event,
    on_status: Callable[[str], None],
    interval_seconds: int = DEFAULT_INTERVAL_SECONDS,
    max_cycles: int | None = None,
) -> int:
    """Run the bounded social cycle until stopped; intended for Ctrl+C interruption."""
    if interval_seconds < MIN_INTERVAL_SECONDS:
        raise ValueError("interval_seconds must be at least 1800 (30 minutes)")
    if max_cycles is not None and max_cycles < 1:
        raise ValueError("max_cycles must be positive when provided")
    cycles = 0
    while not stop_event.is_set() and (max_cycles is None or cycles < max_cycles):
        cycles += 1
        try:
            on_status(f"Cycle {cycles}: {cycle()}")
        except Exception as exc:
            on_status(f"Cycle {cycles}: failed safely ({type(exc).__name__}); will retry later.")
        if max_cycles is not None and cycles >= max_cycles:
            break
        if stop_event.wait(interval_seconds):
            break
    return cycles
