"""Minimal Ollama chat client implemented with the Python standard library."""

from __future__ import annotations

import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class OllamaError(RuntimeError):
    """Raised when the local Ollama service cannot complete a request."""


class OllamaClient:
    def __init__(self, base_url: str, model: str, timeout: float = 120.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

    def is_available(self) -> bool:
        request = Request(f"{self.base_url}/api/tags", method="GET")
        try:
            with urlopen(request, timeout=min(self.timeout, 5.0)) as response:
                return response.status == 200
        except (HTTPError, URLError, TimeoutError, OSError):
            return False

    def chat(self, messages: list[dict[str, str]]) -> str:
        payload = json.dumps(
            {"model": self.model, "messages": messages, "stream": False}
        ).encode("utf-8")
        request = Request(
            f"{self.base_url}/api/chat",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.timeout) as response:
                result = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:500]
            raise OllamaError(f"Ollama returned HTTP {exc.code}: {detail}") from exc
        except (URLError, TimeoutError, OSError) as exc:
            raise OllamaError(
                "Cannot reach Ollama. Make sure Ollama is running on this computer."
            ) from exc
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise OllamaError("Ollama returned an invalid response.") from exc

        try:
            content = result["message"]["content"]
        except (KeyError, TypeError) as exc:
            raise OllamaError("Ollama response did not contain message content.") from exc
        if not isinstance(content, str) or not content.strip():
            raise OllamaError("Ollama returned an empty answer.")
        return content.strip()
