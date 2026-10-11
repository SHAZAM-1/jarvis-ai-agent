"""A conservative, interruptible loop for periodic Moltbook observation."""

from __future__ import annotations

from collections.abc import Callable
from threading import Event

MIN_INTERVAL_SECONDS = 30 * 60
DEFAULT_INTERVAL_SECONDS = 60 * 60


def run_growth_loop(
    fetch_posts: Callable[[], list[dict[str, str]]],
    analyze_posts: Callable[[list[dict[str, str]]], str],
    *,
    stop_event: Event,
    on_report: Callable[[str], None],
    interval_seconds: int = DEFAULT_INTERVAL_SECONDS,
    max_cycles: int | None = None,
) -> int:
    """Observe periodically until stopped; never engage with other agents.

    The 30-minute minimum is intentionally conservative. max_cycles is
    primarily useful for deterministic tests; normal CLI use runs until Ctrl+C.
    Returns the number of cycles attempted.
    """
    if interval_seconds < MIN_INTERVAL_SECONDS:
        raise ValueError(
            f"interval_seconds must be at least {MIN_INTERVAL_SECONDS} (30 minutes)"
        )
    if max_cycles is not None and max_cycles < 1:
        raise ValueError("max_cycles must be positive when provided")

    cycles = 0
    while not stop_event.is_set() and (max_cycles is None or cycles < max_cycles):
        cycles += 1
        try:
            posts = fetch_posts()
            if posts:
                report = analyze_posts(posts)
                on_report(f"Cycle {cycles}: analyzed {len(posts)} posts.\n{report}")
            else:
                on_report(f"Cycle {cycles}: no public posts were returned.")
        except Exception as exc:
            # Keep the loop alive after transient failures, but don't dump
            # exception details that could accidentally contain request data.
            on_report(
                f"Cycle {cycles}: observation failed ({type(exc).__name__}). "
                "Will retry after the configured interval."
            )

        if max_cycles is not None and cycles >= max_cycles:
            break
        if stop_event.wait(interval_seconds):
            break
    return cycles
