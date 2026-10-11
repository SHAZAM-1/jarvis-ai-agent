import pytest

from jarvis.config import Settings


def test_defaults_are_local_and_lightweight(monkeypatch):
    for name in (
        "JARVIS_OLLAMA_URL",
        "JARVIS_MODEL",
        "JARVIS_DB_PATH",
        "JARVIS_REQUEST_TIMEOUT",
        "MOLTBOOK_API_KEY",
    ):
        monkeypatch.delenv(name, raising=False)
    settings = Settings.from_env()
    assert settings.ollama_url == "http://localhost:11434"
    assert settings.model == "qwen3.5:2b"
    assert settings.request_timeout > 0
    assert settings.moltbook_api_key is None


def test_optional_moltbook_key_is_read_from_environment(monkeypatch):
    monkeypatch.setenv("MOLTBOOK_API_KEY", "  example-key  ")
    assert Settings.from_env().moltbook_api_key == "example-key"


def test_invalid_timeout_is_rejected(monkeypatch):
    monkeypatch.setenv("JARVIS_REQUEST_TIMEOUT", "not-a-number")
    with pytest.raises(ValueError):
        Settings.from_env()


def test_invalid_url_is_rejected(monkeypatch):
    monkeypatch.setenv("JARVIS_OLLAMA_URL", "localhost:11434")
    with pytest.raises(ValueError):
        Settings.from_env()
