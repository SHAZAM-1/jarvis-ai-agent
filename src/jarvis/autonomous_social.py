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
    contains_link,
)
from jarvis.social_state import SocialState

# Moltbook's documented limits are higher; Jarvis deliberately stays far below them.
MIN_INTERVAL_SECONDS = 10 * 60
DEFAULT_INTERVAL_SECONDS = 10 * 60
MAX_COMMENTS_PER_UTC_DAY = 5
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
    if contains_link(cleaned) or _CREDENTIAL_RE.search(cleaned):
        return None
    if cleaned.casefold().strip(" .!?") in _GENERIC_REPLIES:
        return None
    context = f"{matching.get('title', '')} {matching.get('content', '')}".strip()
    if len(context) < 20:
        return None
    return {"action": "comment", "post_id": post_id, "content": cleaned}



_PUBLICATION_CREDENTIAL_RE = re.compile(
    r"\b(password|api[ -]?key|secret|seed phrase|private key|token)\b",
    re.IGNORECASE,
)
_FALSE_EXPERIENCE_RE = re.compile(
    r"\b(i (personally )?(built|created|tested|used|discovered|experienced|visited))\b",
    re.IGNORECASE,
)
_ENGAGEMENT_BAIT_RE = re.compile(
    r"\b(follow me|upvote|like and share|dm me|message me for|subscribe to me)\b",
    re.IGNORECASE,
)


def parse_publication_decision(
    raw: str, posts: list[dict[str, str]]
) -> dict[str, str] | None:
    """Validate original-post output and constrain its category to the observed feed."""
    try:
        decision = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return None
    if not isinstance(decision, dict):
        return None
    if decision.get("action") == "skip":
        return {"action": "skip", "submolt": "", "title": "", "content": ""}
    title = decision.get("title")
    content = decision.get("content")
    submolt = decision.get("submolt")
    if decision.get("action") != "publish":
        return None
    if not all(isinstance(value, str) for value in (title, content, submolt)):
        return None
    title = title.strip()
    content = content.strip()
    if not 12 <= len(title) <= 160 or not 120 <= len(content) <= 1800:
        return None
    if contains_link(title + " " + content):
        return None
    if _PUBLICATION_CREDENTIAL_RE.search(title + " " + content):
        return None
    if _FALSE_EXPERIENCE_RE.search(title + " " + content):
        return None
    if _ENGAGEMENT_BAIT_RE.search(title + " " + content):
        return None
    allowed_submolts = {
        post.get("submolt", "").casefold()
        for post in posts
        if isinstance(post.get("submolt"), str) and post.get("submolt")
    }
    if not submolt or submolt.casefold() not in allowed_submolts:
        return None
    return {
        "action": "publish",
        "submolt": submolt,
        "title": title,
        "content": content,
    }


def run_autonomous_publication(
    client: MoltbookClient,
    state: SocialState,
    posts: list[dict[str, str]],
    generate: Callable[[list[dict[str, str]]], str],
    *,
    on_status: Callable[[str], None] = print,
) -> str:
    """Publish at most one original post per rolling 24 hours, if genuinely useful."""
    decision = parse_publication_decision(generate(posts), posts)
    if decision is None:
        return "Publication decision failed validation; no post made."
    if decision["action"] == "skip":
        return "No sufficiently useful original post was identified; skipped."
    publication_id = state.reserve_publication(
        decision["title"], decision["content"], cooldown_hours=24
    )
    if publication_id is None:
        return "Post cooldown or duplicate-content guard blocked publication."
    try:
        client.create_post(
            decision["submolt"], decision["title"], decision["content"]
        )
    except Exception as exc:
        state.record_publication_outcome(
            publication_id, "failed", type(exc).__name__
        )
        on_status(
            f"Post attempt failed safely ({type(exc).__name__}); no automatic retry."
        )
        return "Post attempt failed; no automatic retry."
    state.record_publication_outcome(
        publication_id, "published", "API accepted post request"
    )
    return f"Original post submitted to {decision['submolt']}."



def run_autonomous_cycle(
    client: MoltbookClient,
    state: SocialState,
    generate: Callable[[list[dict[str, str]]], str],
    *,
    on_status: Callable[[str], None] = print,
    generate_publication: Callable[[list[dict[str, str]]], str] | None = None,
) -> str:
    """Fetch, decide, validate and at most perform one social action per cycle."""
    posts = client.fetch_posts(limit=MAX_POSTS, sort="new")
    if not posts:
        return "No public posts returned; no action taken."
    raw = generate(posts)
    decision = parse_engagement_decision(raw, posts)
    if decision is None:
        return "Model decision failed validation; no action taken."
    if decision["action"] == "skip":
        if generate_publication is not None:
            return run_autonomous_publication(
                client, state, posts, generate_publication, on_status=on_status
            )
        return "No post clearly merited a reply; skipped."
    post_id = decision["post_id"]
    if not state.reserve_comment(post_id, daily_limit=MAX_COMMENTS_PER_UTC_DAY):
        return "Daily comment limit reached or post already attempted; skipped."
    try:
        client.create_comment(post_id, decision["content"])
    except Exception as exc:
        state.record_outcome(post_id, "failed", type(exc).__name__)
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
        raise ValueError("interval_seconds must be at least 600 (10 minutes)")
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
