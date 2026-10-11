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
        "JARVIS_AUTONOMOUS_DEVELOPMENT",
        "JARVIS_APPROVED_SOCIAL_LINKS",
    ):
        monkeypatch.delenv(name, raising=False)
    settings = Settings.from_env()
    assert settings.ollama_url == "http://localhost:11434"
    assert settings.model == "qwen3.5:2b"
    assert settings.request_timeout > 0
    assert settings.moltbook_api_key is None
    assert settings.autonomous_social is False
    assert settings.autonomous_development is False


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



@pytest.mark.parametrize("value", ["true", "1", "yes", "on", "TRUE"])
def test_autonomous_development_requires_explicit_truthy_opt_in(monkeypatch, value):
    monkeypatch.setenv("JARVIS_AUTONOMOUS_DEVELOPMENT", value)
    assert Settings.from_env().autonomous_development is True


@pytest.mark.parametrize("value", ["false", "0", "no", "off"])
def test_autonomous_development_can_be_disabled(monkeypatch, value):
    monkeypatch.setenv("JARVIS_AUTONOMOUS_DEVELOPMENT", value)
    assert Settings.from_env().autonomous_development is False


def test_approved_social_links_require_exact_https_urls(monkeypatch):
    monkeypatch.setenv(
        "JARVIS_APPROVED_SOCIAL_LINKS",
        " https://example.com/project,https://github.com/owner/repo,https://example.com/project "
    )
    assert Settings.from_env().approved_social_links == (
        "https://example.com/project",
        "https://github.com/owner/repo",
    )


@pytest.mark.parametrize(
    "link",
    [
        "http://example.com",
        "https://user:pass@example.com",
        "https://example.com:8443/path",
        "https://example.com/path#fragment",
        "javascript:alert(1)",
    ],
)
def test_approved_social_links_reject_unsafe_url_forms(monkeypatch, link):
    monkeypatch.setenv("JARVIS_APPROVED_SOCIAL_LINKS", link)
    with pytest.raises(ValueError, match="JARVIS_APPROVED_SOCIAL_LINKS"):
        Settings.from_env()


@pytest.mark.parametrize("value", ["nan", "NaN", "inf", "-inf", "0", "-1"])
def test_non_finite_or_non_positive_timeout_is_rejected(monkeypatch, value):
    monkeypatch.setenv("JARVIS_REQUEST_TIMEOUT", value)
    with pytest.raises(ValueError, match="finite number greater than zero"):
        Settings.from_env()


@pytest.mark.parametrize(
    "value",
    [
        "http://",
        "https:///path",
        "http://localhost:badport",
        "http://user:password@localhost:11434",
        "http://localhost:11434?debug=1",
        "http://localhost:11434#fragment",
    ],
)
def test_malformed_or_credential_bearing_ollama_urls_are_rejected(monkeypatch, value):
    monkeypatch.setenv("JARVIS_OLLAMA_URL", value)
    with pytest.raises(ValueError, match="JARVIS_OLLAMA_URL"):
        Settings.from_env()
