from threading import Event

import pytest

from jarvis.moltbook_loop import (
    DEFAULT_INTERVAL_SECONDS,
    MIN_INTERVAL_SECONDS,
    run_growth_loop,
)


class ImmediateEvent(Event):
    def wait(self, timeout=None):
        return False


def test_growth_loop_runs_bounded_cycles_and_reports_analysis():
    reports = []
    calls = []
    posts = [{"title": "Hello", "author": "agent", "submolt": "general", "content": "Hi"}]

    cycles = run_growth_loop(
        lambda: calls.append("fetch") or posts,
        lambda items: f"analyzed {len(items)}",
        stop_event=ImmediateEvent(),
        on_report=reports.append,
        interval_seconds=MIN_INTERVAL_SECONDS,
        max_cycles=2,
    )

    assert cycles == 2
    assert calls == ["fetch", "fetch"]
    assert reports == [
        "Cycle 1: analyzed 1 posts.\nanalyzed 1",
        "Cycle 2: analyzed 1 posts.\nanalyzed 1",
    ]


def test_growth_loop_rejects_too_frequent_polling():
    with pytest.raises(ValueError, match="at least"):
        run_growth_loop(
            lambda: [],
            lambda posts: "",
            stop_event=Event(),
            on_report=lambda report: None,
            interval_seconds=60,
            max_cycles=1,
        )


def test_growth_loop_survives_transient_failure_without_printing_exception_text():
    reports = []

    def fail():
        raise RuntimeError("sensitive details should not be shown")

    cycles = run_growth_loop(
        fail,
        lambda posts: "",
        stop_event=ImmediateEvent(),
        on_report=reports.append,
        interval_seconds=DEFAULT_INTERVAL_SECONDS,
        max_cycles=1,
    )

    assert cycles == 1
    assert "RuntimeError" in reports[0]
    assert "sensitive details" not in reports[0]


def test_growth_loop_reports_empty_feed():
    reports = []
    run_growth_loop(
        lambda: [],
        lambda posts: "not called",
        stop_event=ImmediateEvent(),
        on_report=reports.append,
        interval_seconds=DEFAULT_INTERVAL_SECONDS,
        max_cycles=1,
    )
    assert reports == ["Cycle 1: no public posts were returned."]
