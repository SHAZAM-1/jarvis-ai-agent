"""Persistent local conversation storage and user-approved learning notes."""

from __future__ import annotations

import pathlib
import sqlite3


_CONVERSATION_ROLES = frozenset({"user", "assistant"})


class MemoryStore:
    def __init__(self, db_path: str | pathlib.Path) -> None:
        self.db_path = pathlib.Path(db_path)
        if str(self.db_path) != ":memory:":
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(str(self.db_path), timeout=10)

    def _initialize(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    role TEXT NOT NULL CHECK(role IN ('system', 'user', 'assistant')),
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )"""
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_messages_id ON messages(id)")
            conn.execute(
                """CREATE TABLE IF NOT EXISTS lessons (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    lesson TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )"""
            )

    def add_message(self, role: str, content: str) -> int:
        # System instructions are constructed by the application, never persisted
        # as replayable conversation history. Keep the database schema compatible
        # with existing files, but reject privileged roles at this write boundary.
        if not isinstance(role, str) or role not in _CONVERSATION_ROLES:
            raise ValueError("role must be user or assistant")
        if not isinstance(content, str) or not content.strip():
            raise ValueError("content must be a non-empty string")
        with self._connect() as conn:
            cursor = conn.execute(
                "INSERT INTO messages(role, content) VALUES (?, ?)",
                (role, content.strip()),
            )
            return int(cursor.lastrowid)

    def recent_messages(self, limit: int = 12) -> list[dict[str, str]]:
        if limit < 1:
            raise ValueError("limit must be at least 1")
        with self._connect() as conn:
            rows = conn.execute(
                """SELECT role, content FROM messages
                   WHERE role IN (?, ?)
                   ORDER BY id DESC LIMIT ?""",
                ("user", "assistant", limit),
            ).fetchall()
        # Filter at retrieval, before applying the limit, so legacy/externally
        # written privileged or malformed rows cannot be replayed or crowd out
        # legitimate conversation history.
        return [
            {"role": role, "content": content}
            for role, content in reversed(rows)
            if role in _CONVERSATION_ROLES and isinstance(content, str) and content.strip()
        ]

    def add_lesson(self, lesson: str) -> int:
        """Save an explicit user-approved correction, preference, or lesson."""
        if not isinstance(lesson, str) or not lesson.strip():
            raise ValueError("lesson must be a non-empty string")
        cleaned = lesson.strip()
        if len(cleaned) > 2000:
            raise ValueError("lesson must be 2000 characters or fewer")
        with self._connect() as conn:
            cursor = conn.execute("INSERT INTO lessons(lesson) VALUES (?)", (cleaned,))
            return int(cursor.lastrowid)

    def recent_lessons(self, limit: int = 20) -> list[dict[str, str | int]]:
        if limit < 1:
            raise ValueError("limit must be at least 1")
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id, lesson, created_at FROM lessons ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [
            {"id": row_id, "lesson": lesson, "created_at": created_at}
            for row_id, lesson, created_at in reversed(rows)
        ]

    def delete_lesson(self, lesson_id: int) -> bool:
        if lesson_id < 1:
            raise ValueError("lesson_id must be positive")
        with self._connect() as conn:
            cursor = conn.execute("DELETE FROM lessons WHERE id = ?", (lesson_id,))
            return cursor.rowcount > 0

    def clear(self) -> None:
        """Clear conversation history without deleting learned notes."""
        with self._connect() as conn:
            conn.execute("DELETE FROM messages")
