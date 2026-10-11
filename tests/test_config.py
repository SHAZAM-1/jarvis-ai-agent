import pytest

from jarvis.config import Settings


def test_defaults_are_local_and_lightweight(monkeypatch):
    for name in (
        "JARVIS_OLLAMA_URL", "JARVIS_MODEL", "JARVIS_DB_PATH", "JARVIS_REQUEST_TIMEOUT"
    ):
        monkeypatch.delenv(name, raising=False)
    settings = Settings.from_env()
    assert settings.ollama_url == "http://localhost:11434"
    assert settings.model == "qwen3.5:2b"
    assert settings.request_timeout > 0


def test_invalid_timeout_is_rejected(monkeypatch):
    monkeypatch.setenv("JARVIS_REQUEST_TIMEOUT", "not-a-number")
    with pytest.raises(ValueError):
        Settings.from_env()


def test_invalid_url_is_rejected(monkeypatch):
    monkeypatch.setenv("JARVIS_OLLAMA_URL", "localhost:11434")
    with pytest.raises(ValueError):
        Settings.from_env()
