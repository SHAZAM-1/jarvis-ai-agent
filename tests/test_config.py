import pytest

from jarvis.config import Settings


def test_defaults_are_local_and_lightweight(monkeypatch):
    for name in (
        "JARVIS_OLLAMA_URL",
        "JARVIS_MODEL",
        "JARVIS_DB_PATH",
        "JARVIS_REQUEST_TIMEOUT",
        "MOLTBOOK_API_KEY",
        "JARVIS_AUTONOMOUS_SOCIAL",
    ):
        monkeypatch.delenv(name, raising=False)
    settings = Settings.from_env()
    assert settings.ollama_url == "http://localhost:11434"
    assert settings.model == "qwen3.5:2b"
    assert settings.request_timeout > 0
    assert settings.moltbook_api_key is None
    assert settings.autonomous_social is False


def test_optional_moltbook_key_is_read_from_environment(monkeypatch):
    monkeypatch.setenv("MOLTBOOK_API_KEY", "  example-key  ")
    assert Settings.from_env().moltbook_api_key == "example-key"


@pytest.mark.parametrize("value", ["true", "1", "yes", "on", "TRUE"])
def test_autonomous_social_requires_explicit_truthy_opt_in(monkeypatch, value):
    monkeypatch.setenv("JARVIS_AUTONOMOUS_SOCIAL", value)
    assert Settings.from_env().autonomous_social is True


@pytest.mark.parametrize("value", ["false", "0", "no", "off"])
def test_autonomous_social_can_be_explicitly_disabled(monkeypatch, value):
    monkeypatch.setenv("JARVIS_AUTONOMOUS_SOCIAL", value)
    assert Settings.from_env().autonomous_social is False


def test_invalid_boolean_is_rejected(monkeypatch):
    monkeypatch.setenv("JARVIS_AUTONOMOUS_SOCIAL", "maybe")
    with pytest.raises(ValueError, match="JARVIS_AUTONOMOUS_SOCIAL"):
        Settings.from_env()


def test_invalid_timeout_is_rejected(monkeypatch):
    monkeypatch.setenv("JARVIS_REQUEST_TIMEOUT", "not-a-number")
    with pytest.raises(ValueError):
        Settings.from_env()


def test_invalid_url_is_rejected(monkeypatch):
    monkeypatch.setenv("JARVIS_OLLAMA_URL", "localhost:11434")
    with pytest.raises(ValueError):
        Settings.from_env()
