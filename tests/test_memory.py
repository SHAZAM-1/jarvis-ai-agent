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


def test_learning_notes_persist_and_can_be_deleted(tmp_path):
    memory = MemoryStore(tmp_path / "memory.sqlite3")
    lesson_id = memory.add_lesson("Prefer concise answers in Darija.")

    assert memory.recent_lessons() == [
        {
            "id": lesson_id,
            "lesson": "Prefer concise answers in Darija.",
            "created_at": memory.recent_lessons()[0]["created_at"],
        }
    ]
    assert memory.delete_lesson(lesson_id) is True
    assert memory.recent_lessons() == []
    assert memory.delete_lesson(lesson_id) is False


def test_clear_preserves_learning_notes(tmp_path):
    memory = MemoryStore(tmp_path / "memory.sqlite3")
    memory.add_message("user", "hello")
    memory.add_lesson("Use metric units.")

    memory.clear()

    assert memory.recent_messages() == []
    assert len(memory.recent_lessons()) == 1


@pytest.mark.parametrize("lesson", ["", "  ", None])
def test_empty_learning_notes_are_rejected(tmp_path, lesson):
    memory = MemoryStore(tmp_path / "memory.sqlite3")
    with pytest.raises(ValueError):
        memory.add_lesson(lesson)


def test_learning_note_length_is_limited(tmp_path):
    memory = MemoryStore(tmp_path / "memory.sqlite3")
    with pytest.raises(ValueError):
        memory.add_lesson("x" * 2001)
