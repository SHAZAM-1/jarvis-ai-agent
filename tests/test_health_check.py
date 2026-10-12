from __future__ import annotations

import subprocess
from pathlib import Path

from jarvis.health_check import ProjectHealthCheckAgent


class FakeLLM:
    def __init__(self, available: bool = True) -> None:
        self.available = available
        self.messages = None
        self.calls: list[list[dict[str, str]]] = []

    def is_available(self) -> bool:
        return self.available

    def chat(self, messages: list[dict[str, str]]) -> str:
        self.messages = messages
        self.calls.append(messages)
        return "Status: one test finding; prioritize the smallest safe fix."


def _git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
        shell=False,
    )
    return result.stdout.strip()


def _repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-b", "main")
    _git(root, "config", "user.email", "test@example.com")
    _git(root, "config", "user.name", "Health Check Test")
    (root / "README.md").write_text("# Jarvis test repository\n", encoding="utf-8")
    (root / "sample.py").write_text('API_TOKEN = "private-test-token-value"\nvalue = 1\n', encoding="utf-8")
    _git(root, "add", "README.md", "sample.py")
    _git(root, "commit", "-m", "test fixture")
    return root


def test_health_check_inventories_files_and_contacts_local_model(tmp_path):
    root = _repo(tmp_path)
    llm = FakeLLM()
    agent = ProjectHealthCheckAgent(llm, root, model_name="local-test-model")

    report = agent.run(run_quality_gates=False)

    assert "JARVIS PROJECT HEALTH CHECK" in report
    assert "project paths inventoried: 2" in report
    assert "read-only diagnosis" in report
    assert "one test finding" in report
    assert llm.messages is not None
    prompts = "\\n".join(
        message["content"]
        for call in llm.calls
        for message in call
    )
    assert "sample.py" in prompts
    assert "RECENT HISTORY ACROSS REFS" in prompts
    assert "private-test-token-value" not in prompts
    assert "[REDACTED]" in prompts
    assert _git(root, "status", "--porcelain") == ""


def test_health_check_skips_model_when_local_ollama_is_unavailable(tmp_path):
    root = _repo(tmp_path)
    llm = FakeLLM(available=False)
    report = ProjectHealthCheckAgent(llm, root).run(run_quality_gates=False)

    assert "PARTIAL" in report
    assert "Ollama is not responding" in report
    assert llm.messages is None


def test_health_check_quality_gates_are_fixed_and_never_autofix(tmp_path, monkeypatch):
    root = _repo(tmp_path)
    agent = ProjectHealthCheckAgent(FakeLLM(), root)
    seen: list[list[str]] = []

    def fake_run(args: list[str], timeout: int = 30):
        seen.append(args)
        return type("Result", (), {"name": " ".join(args), "ok": True, "summary": "ok"})()

    monkeypatch.setattr(agent, "_run", fake_run)
    checks = agent._quality_checks()

    assert len(checks) == 3
    assert any(args[-3:] == ["ruff", "check", "src"] for args in seen) is False
    assert seen[0][-4:] == ["ruff", "check", "src", "tests"]
    assert seen[1][-4:] == ["compileall", "-q", "src", "tests"]
    assert seen[2][-2:] == ["pytest", "-q"]
    assert all("--fix" not in args for args in seen)


def test_redaction_handles_bearer_and_assignment_secrets():
    text = 'MOLTBOOK_API_KEY = "private-token-value"\nAuthorization: Bearer abcdefghijklmnopqrstuvwxyz123'
    redacted = ProjectHealthCheckAgent._redact(text)
    assert "private-token-value" not in redacted
    assert "abcdefghijklmnopqrstuvwxyz123" not in redacted
    assert "[REDACTED]" in redacted
