from jarvis.memory import MemoryStore
import pytest


def test_messages_are_saved_and_returned_in_chronological_order(tmp_path):
    memory = MemoryStore(tmp_path / "memory.sqlite3")
    memory.add_message("user", "hello")
    memory.add_message("assistant", "hi")

    assert memory.recent_messages() == [
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "hi"},
    ]


def test_recent_messages_respects_limit(tmp_path):
    memory = MemoryStore(tmp_path / "memory.sqlite3")
    for number in range(3):
        memory.add_message("user", str(number))

    assert memory.recent_messages(2) == [
        {"role": "user", "content": "1"},
        {"role": "user", "content": "2"},
    ]


def test_invalid_role_and_empty_content_are_rejected(tmp_path):
    memory = MemoryStore(tmp_path / "memory.sqlite3")
    with pytest.raises(ValueError):
        memory.add_message("admin", "not allowed")
    with pytest.raises(ValueError):
        memory.add_message("user", "  ")


def test_clear_removes_saved_messages(tmp_path):
    memory = MemoryStore(tmp_path / "memory.sqlite3")
    memory.add_message("user", "hello")
    memory.clear()
    assert memory.recent_messages() == []
