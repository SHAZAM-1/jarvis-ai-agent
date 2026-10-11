"""Persistent, local-only conversation storage using SQLite."""

from __future__ import annotations

import sqlite3
from pathlib import Path


class MemoryStore:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
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
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_messages_id ON messages(id)"
            )

    def add_message(self, role: str, content: str) -> int:
        if role not in {"system", "user", "assistant"}:
            raise ValueError("role must be system, user, or assistant")
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
                "SELECT role, content FROM messages ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [{"role": role, "content": content} for role, content in reversed(rows)]

    def clear(self) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM messages")
