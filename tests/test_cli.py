from __future__ import annotations

from jarvis.cli import _print_status
from jarvis.config import Settings


class FakeOllama:
    def __init__(self, available: bool) -> None:
        self.available = available

    def is_available(self) -> bool:
        return self.available


def test_status_reports_health_and_safety_flags_without_leaking_secrets(capsys):
    secret = "never-print-this-api-key"
    private_url = "https://example.com/private-resource"
    settings = Settings(
        model="qwen3.5:2b",
        moltbook_api_key=secret,
        autonomous_social=True,
        autonomous_development=False,
        approved_social_links=(private_url,),
    )

    _print_status(settings, FakeOllama(available=True))

    output = capsys.readouterr().out
    assert "Ollama service: available" in output
    assert "Model: qwen3.5:2b" in output
    assert "Moltbook API key: configured (value hidden)" in output
    assert "Autonomous social: ENABLED" in output
    assert "Autonomous development: disabled" in output
    assert "1 configured (URLs hidden)" in output
    assert secret not in output
    assert private_url not in output


def test_status_reports_unavailable_ollama_and_disabled_social(capsys):
    settings = Settings()
    _print_status(settings, FakeOllama(available=False))
    output = capsys.readouterr().out
    assert "Ollama service: not responding" in output
    assert "Moltbook API key: not configured" in output
    assert "Autonomous social: disabled" in output
    assert "Autonomous development: disabled" in output
