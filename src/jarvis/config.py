"""Small, dependency-free configuration for Jarvis."""

from __future__ import annotations

import math
import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit


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
    autonomous_development: bool = False
    approved_social_links: tuple[str, ...] = ()

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
        try:
            parsed_url = urlsplit(url)
            parsed_url.port  # Force validation of any explicit port.
        except ValueError as exc:
            raise ValueError("JARVIS_OLLAMA_URL must be a valid HTTP(S) URL.") from exc
        if (
            parsed_url.scheme not in {"http", "https"}
            or not parsed_url.hostname
            or parsed_url.username is not None
            or parsed_url.password is not None
            or parsed_url.query
            or parsed_url.fragment
        ):
            raise ValueError(
                "JARVIS_OLLAMA_URL must be a valid HTTP(S) URL without credentials, "
                "query parameters, or fragments."
            )
        if not model:
            raise ValueError("JARVIS_MODEL cannot be empty.")
        if not math.isfinite(timeout) or timeout <= 0:
            raise ValueError(
                "JARVIS_REQUEST_TIMEOUT must be a finite number greater than zero."
            )
        api_key = os.getenv("MOLTBOOK_API_KEY", "").strip() or None
        autonomous_social = _env_bool("JARVIS_AUTONOMOUS_SOCIAL", default=False)
        autonomous_development = _env_bool(
            "JARVIS_AUTONOMOUS_DEVELOPMENT", default=False
        )
        raw_links = os.getenv("JARVIS_APPROVED_SOCIAL_LINKS", "")
        approved_links: list[str] = []
        for raw_link in raw_links.split(","):
            link = raw_link.strip()
            if not link:
                continue
            parsed = urlsplit(link)
            if (
                parsed.scheme != "https"
                or not parsed.hostname
                or parsed.username is not None
                or parsed.password is not None
                or parsed.port is not None
                or parsed.fragment
                or any(character.isspace() for character in link)
            ):
                raise ValueError(
                    "JARVIS_APPROVED_SOCIAL_LINKS accepts only exact HTTPS URLs "
                    "without credentials, ports, fragments, or whitespace."
                )
            if link not in approved_links:
                approved_links.append(link)
        return cls(
            url, model, db_path, timeout, api_key,
            autonomous_social, autonomous_development, tuple(approved_links)
        )
