from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from jarvis.autonomous_social import parse_engagement_decision, run_autonomous_cycle
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
