import json
from unittest.mock import patch

from jarvis.llm.ollama import OllamaClient, OllamaError
import pytest


class FakeResponse:
    status = 200

    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


def test_chat_returns_assistant_content():
    client = OllamaClient("http://localhost:11434", "qwen3.5:2b")
    payload = {"message": {"content": "Hello from Jarvis"}}
    with patch("jarvis.llm.ollama.urlopen", return_value=FakeResponse(payload)):
        assert client.chat([{"role": "user", "content": "hello"}]) == "Hello from Jarvis"


def test_chat_rejects_missing_content():
    client = OllamaClient("http://localhost:11434", "qwen3.5:2b")
    with patch("jarvis.llm.ollama.urlopen", return_value=FakeResponse({})):
        with pytest.raises(OllamaError):
            client.chat([{"role": "user", "content": "hello"}])
