from __future__ import annotations

import json

import pytest

from jarvis.project_mesh import ProjectCrawler, ProjectMesh


class FakeLLM:
    base_url = "http://127.0.0.1:11434"

    def __init__(self, response: str | None = None, *, available: bool = True) -> None:
        self.response = response or json.dumps({"findings": []})
        self.available = available
        self.calls = 0
        self.messages = []

    def is_available(self) -> bool:
        return self.available

    def chat(self, messages):
        self.calls += 1
        self.messages.append(messages)
        return self.response


def test_mesh_broadcast_and_direct_messages_are_shared(tmp_path):
    mesh = ProjectMesh(tmp_path / "mesh.sqlite3")
    mesh.publish("health-check", "finding", "A bounded issue was detected.", kind="finding")
    mesh.publish("guardian", "policy", "Check owner policy before any change.", recipient="self-dev", kind="lesson")

    assert "bounded issue" in mesh.context_for("self-dev")
    assert "owner policy" in mesh.context_for("self-dev")
    assert "Check owner policy before any change." not in mesh.context_for("health-check")


def test_mesh_redacts_secrets_before_persistence(tmp_path):
    mesh = ProjectMesh(tmp_path / "mesh.sqlite3")
    mesh.publish("agent", "config", "API_KEY=secret-value-123")
    mesh.publish("agent", "json-config", '{"ACCESS_TOKEN": "secret-json-value", "safe": true}')
    context = mesh.context_for("agent")

    assert "secret-value-123" not in context
    assert "secret-json-value" not in context
    assert "[REDACTED]" in context


def test_malformed_specialist_output_is_saved_as_unverified_review(tmp_path):
    mesh = ProjectMesh(tmp_path / "mesh.sqlite3")
    count = mesh.record_findings("refs/heads/main", "src/example.py", "security", "not json")

    assert count == 1
    assert "malformed JSON" in mesh.context_for("health-check")


def test_crawler_refuses_non_loopback_model_before_sending_source(tmp_path):
    class RemoteLLM(FakeLLM):
        base_url = "https://example.invalid"

        def is_available(self):
            raise AssertionError("remote model must not be contacted")

    mesh = ProjectMesh(tmp_path / "mesh.sqlite3")
    crawler = ProjectCrawler(RemoteLLM(), tmp_path, mesh)

    with pytest.raises(RuntimeError, match="non-loopback"):
        crawler.crawl()


def test_crawler_refuses_when_local_model_unavailable(tmp_path):
    mesh = ProjectMesh(tmp_path / "mesh.sqlite3")
    crawler = ProjectCrawler(FakeLLM(available=False), tmp_path, mesh)

    with pytest.raises(RuntimeError, match="unavailable"):
        crawler.crawl()


def test_crawler_refuses_unknown_endpoint_before_contact(tmp_path):
    class UnknownEndpointLLM:
        def is_available(self):
            raise AssertionError("unknown endpoint must not be contacted")

    mesh = ProjectMesh(tmp_path / "mesh.sqlite3")
    crawler = ProjectCrawler(UnknownEndpointLLM(), tmp_path, mesh)

    with pytest.raises(RuntimeError, match="unknown model endpoint"):
        crawler.crawl()


def test_crawler_context_is_bounded_and_status_is_honest(tmp_path):
    mesh = ProjectMesh(tmp_path / "mesh.sqlite3")
    mesh.publish("crawler", "report", "This is a preliminary finding.", kind="finding")
    status = ProjectCrawler(FakeLLM(), tmp_path, mesh).status()

    assert "no crawl recorded yet" in status
    assert "preliminary finding" in mesh.context_for("self-dev")


def test_specialist_uses_crawler_output_schema_and_shares_findings(tmp_path):
    response = json.dumps(
        {
            "findings": [
                {
                    "severity": "medium",
                    "summary": "Missing input validation in the example.",
                    "evidence": "value is used before validation",
                }
            ]
        }
    )
    llm = FakeLLM(response)
    mesh = ProjectMesh(tmp_path / "mesh.sqlite3")
    crawler = ProjectCrawler(llm, tmp_path, mesh)

    result = crawler._analyze(
        ("refs/heads/main", "src/example.py", "tests and correctness", "value = input()")
    )

    assert result[4] == 1
    assert "required output schema" in llm.messages[0][0]["content"]
    assert "Missing input validation" in mesh.context_for("health-check")


def test_crawler_reads_safe_worktree_files_and_excludes_sensitive_paths(tmp_path):
    source = tmp_path / "src" / "example.py"
    source.parent.mkdir()
    source.write_text('API_KEY = "secret-worktree-value"\nvalue = 1\n', encoding="utf-8")
    private = tmp_path / "secrets" / "settings.py"
    private.parent.mkdir()
    private.write_text("private = True\n", encoding="utf-8")

    crawler = ProjectCrawler(FakeLLM(), tmp_path, ProjectMesh(tmp_path / "mesh.sqlite3"))

    content = crawler._read_ref_file("WORKTREE", "src/example.py")
    assert content is not None
    assert "secret-worktree-value" not in content
    assert "[REDACTED]" in content
    assert crawler._read_ref_file("WORKTREE", "secrets/settings.py") is None
    assert crawler._read_ref_file("WORKTREE", "../outside.py") is None
