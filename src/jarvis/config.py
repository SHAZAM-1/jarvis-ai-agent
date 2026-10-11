"""Small, dependency-free configuration for Jarvis."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    value = raw.strip().lower()
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{name} must be true/false, yes/no, on/off, or 1/0.")


@dataclass(frozen=True, slots=True)
class Settings:
    ollama_url: str = "http://localhost:11434"
    model: str = "qwen3.5:2b"
    db_path: Path = Path("data/jarvis.db")
    request_timeout: float = 120.0
    moltbook_api_key: str | None = None
    autonomous_social: bool = False

    @classmethod
    def from_env(cls) -> "Settings":
        defaults = cls()
        url = os.getenv("JARVIS_OLLAMA_URL", defaults.ollama_url).strip().rstrip("/")
        model = os.getenv("JARVIS_MODEL", defaults.model).strip()
        db_path = Path(os.getenv("JARVIS_DB_PATH", str(defaults.db_path))).expanduser()
        raw_timeout = os.getenv("JARVIS_REQUEST_TIMEOUT", str(defaults.request_timeout))
        try:
            timeout = float(raw_timeout)
        except ValueError as exc:
            raise ValueError("JARVIS_REQUEST_TIMEOUT must be a number.") from exc
        if not url.startswith(("http://", "https://")):
            raise ValueError("JARVIS_OLLAMA_URL must start with http:// or https://.")
        if not model:
            raise ValueError("JARVIS_MODEL cannot be empty.")
        if timeout <= 0:
            raise ValueError("JARVIS_REQUEST_TIMEOUT must be greater than zero.")
        api_key = os.getenv("MOLTBOOK_API_KEY", "").strip() or None
        autonomous_social = _env_bool("JARVIS_AUTONOMOUS_SOCIAL", default=False)
        return cls(url, model, db_path, timeout, api_key, autonomous_social)
