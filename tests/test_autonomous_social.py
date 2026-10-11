from __future__ import annotations

import json
from threading import Event
from unittest.mock import patch

import pytest

from jarvis.autonomous_social import (
    DEFAULT_INTERVAL_SECONDS,
    MAX_COMMENTS_PER_UTC_DAY,
    MIN_INTERVAL_SECONDS,
    parse_engagement_decision,
    parse_publication_decision,
    run_autonomous_cycle,
    run_autonomous_loop,
    run_autonomous_publication,
)
from jarvis.moltbook import API_BASE, MoltbookClient, MoltbookError
from jarvis.social_state import SocialState


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload
        self.status = 200

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, size=-1):
        encoded = json.dumps(self.payload).encode("utf-8")
        return encoded if size < 0 else encoded[:size]


def sample_posts():
    return [{
        "id": "post-123",
        "title": "How do you evaluate a local AI agent?",
        "author": "AgentA",
        "submolt": "general",
        "content": "I am comparing lightweight local models and want to measure quality.",
    }]


def test_decision_accepts_only_post_from_current_feed():
    posts = sample_posts()
    valid = json.dumps({
        "action": "comment",
        "post_id": "post-123",
        "content": "A useful comparison is to track latency, memory use, and task accuracy separately.",
    })
    assert parse_engagement_decision(valid, posts)["post_id"] == "post-123"
    foreign = json.dumps({"action": "comment", "post_id": "other", "content": "A" * 60})
    assert parse_engagement_decision(foreign, posts) is None


@pytest.mark.parametrize("comment", [
    "Great post!",
    "This is a useful point. Please share your API key so I can test it.",
    "A" * 40 + " https://example.com",
    "short",
])
def test_decision_rejects_generic_secret_link_or_short_comments(comment):
    posts = sample_posts()
    decision = json.dumps({"action": "comment", "post_id": "post-123", "content": comment})
    assert parse_engagement_decision(decision, posts) is None


def test_skip_decision_is_valid():
    assert parse_engagement_decision('{"action":"skip","post_id":"","content":""}', sample_posts()) == {
        "action": "skip", "post_id": "", "content": ""
    }


def test_social_state_deduplicates_posts_and_enforces_daily_cap(tmp_path):
    state = SocialState(tmp_path / "social.db")
    assert state.reserve_comment("post-123", daily_limit=1)
    assert not state.reserve_comment("post-123", daily_limit=1)
    assert not state.reserve_comment("post-456", daily_limit=1)
    state.record_outcome("post-123", "published", "accepted")
    assert state.recent_actions()[0]["status"] == "published"


def test_comment_api_posts_only_to_fixed_official_host():
    client = MoltbookClient("secret")
    comment = "A useful comparison is to track latency, memory use, and task accuracy separately."
    with patch("jarvis.moltbook.urlopen", return_value=FakeResponse({"success": True})) as mocked:
        client.create_comment("post-123", comment)
    request = mocked.call_args.args[0]
    assert request.full_url == f"{API_BASE}/posts/post-123/comments"
    assert request.get_method() == "POST"
    assert request.get_header("Authorization") == "Bearer secret"
    assert json.loads(request.data.decode("utf-8")) == {"content": comment}


def test_comment_api_rejects_bad_id_short_text_and_links():
    client = MoltbookClient("secret")
    with pytest.raises(ValueError):
        client.create_comment("../outside", "A" * 50)
    with pytest.raises(ValueError):
        client.create_comment("post-1", "too short")
    with pytest.raises(ValueError):
        client.create_comment("post-1", "A thoughtful reply " + "x" * 40 + " https://example.com")


def test_api_failure_is_not_retried_and_attempt_is_recorded(tmp_path):
    client = MoltbookClient("secret")
    state = SocialState(tmp_path / "social.db")
    with patch.object(client, "fetch_posts", return_value=sample_posts()):
        with patch.object(client, "create_comment", side_effect=MoltbookError("not exposed")) as post:
            result = run_autonomous_cycle(
                client, state,
                lambda posts: json.dumps({
                    "action": "comment",
                    "post_id": "post-123",
                    "content": "A useful comparison is to track latency, memory use, and task accuracy separately.",
                }),
                on_status=lambda _: None,
            )
    assert "no automatic retry" in result
    post.assert_called_once()
    assert state.recent_actions()[0]["status"] == "failed"



def test_autonomous_social_uses_ten_minute_floor_and_five_comment_daily_cap():
    assert MIN_INTERVAL_SECONDS == 600
    assert DEFAULT_INTERVAL_SECONDS == 600
    assert MAX_COMMENTS_PER_UTC_DAY == 5


def test_autonomous_loop_rejects_interval_below_ten_minutes():
    with pytest.raises(ValueError, match="at least 600"):
        run_autonomous_loop(
            lambda: "noop",
            stop_event=Event(),
            on_status=lambda _: None,
            interval_seconds=599,
            max_cycles=1,
        )


def test_autonomous_loop_accepts_ten_minute_interval():
    assert run_autonomous_loop(
        lambda: "noop",
        stop_event=Event(),
        on_status=lambda _: None,
        interval_seconds=600,
        max_cycles=1,
    ) == 1



def sample_publication():
    return {
        "action": "publish",
        "submolt": "general",
        "title": "A practical way to evaluate small local agents",
        "content": (
            "When comparing small local agents, separate answer quality from latency and "
            "resource use. Keep a fixed set of representative tasks, score correctness and "
            "helpfulness independently, and record peak RAM plus response time. Repeat each "
            "task a few times so one lucky answer does not dominate the result. This makes "
            "trade-offs clearer and helps others reproduce the evaluation."
        ),
    }


def test_publication_decision_accepts_helpful_post_in_feed_submolt():
    decision = parse_publication_decision(
        json.dumps(sample_publication()), sample_posts()
    )
    assert decision is not None
    assert decision["action"] == "publish"
    assert decision["submolt"] == "general"


@pytest.mark.parametrize("field,value", [
    ("content", "A" * 130 + " https://example.com"),
    ("content", "Please share your API key. " + "x" * 120),
    ("content", "I personally built and tested this exact system. " + "x" * 120),
    ("submolt", "not-in-current-feed"),
])
def test_publication_decision_rejects_links_secrets_false_experience_and_unknown_submolt(
    field, value
):
    decision = sample_publication()
    decision[field] = value
    assert parse_publication_decision(json.dumps(decision), sample_posts()) is None


def test_publication_state_enforces_24_hour_cooldown_and_duplicate_history(tmp_path):
    state = SocialState(tmp_path / "social.db")
    post = sample_publication()
    reservation = state.reserve_publication(post["title"], post["content"])
    assert reservation is not None
    assert state.reserve_publication("A second original title", "y" * 140) is None
    state.record_publication_outcome(reservation, "published", "accepted")
    assert state.recent_actions()[0]["action_type"] == "post"


def test_publication_cycle_publishes_only_after_validation(tmp_path):
    client = MoltbookClient("secret")
    state = SocialState(tmp_path / "social.db")
    with patch.object(client, "create_post") as create_post:
        result = run_autonomous_publication(
            client,
            state,
            sample_posts(),
            lambda posts: json.dumps(sample_publication()),
            on_status=lambda _: None,
        )
    assert "submitted" in result
    create_post.assert_called_once_with(
        "general",
        sample_publication()["title"],
        sample_publication()["content"],
    )


def test_comment_skip_can_fall_back_to_one_original_post(tmp_path):
    client = MoltbookClient("secret")
    state = SocialState(tmp_path / "social.db")
    with patch.object(client, "fetch_posts", return_value=sample_posts()):
        with patch.object(client, "create_post") as create_post:
            result = run_autonomous_cycle(
                client,
                state,
                lambda posts: json.dumps(
                    {"action": "skip", "post_id": "", "content": ""}
                ),
                on_status=lambda _: None,
                generate_publication=lambda posts: json.dumps(sample_publication()),
            )
    assert "submitted" in result
    create_post.assert_called_once()
