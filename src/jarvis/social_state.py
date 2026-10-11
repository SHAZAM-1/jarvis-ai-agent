"""Persistent, conservative state for autonomous Moltbook engagement."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path


class SocialState:
    """Record comment attempts so restarts cannot cause duplicate engagement."""

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = str(db_path)
        if self.db_path != ":memory:":
            Path(self.db_path).expanduser().parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute(
                """CREATE TABLE IF NOT EXISTS social_actions (
                    post_id TEXT PRIMARY KEY,
                    attempted_at TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'reserved',
                    detail TEXT NOT NULL DEFAULT ''
                )"""
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_social_actions_attempted_at "
                "ON social_actions(attempted_at)"
            )

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path, timeout=10, isolation_level=None)

    @staticmethod
    def _now() -> datetime:
        return datetime.now(UTC)

    def reserve_comment(self, post_id: str, daily_limit: int = 1) -> bool:
        """Atomically reserve one post and enforce a UTC daily attempt limit.

        Failed API attempts also count toward the limit: conservative by design.
        """
        cleaned = post_id.strip() if isinstance(post_id, str) else ""
        if not cleaned or len(cleaned) > 160:
            return False
        if daily_limit < 1:
            raise ValueError("daily_limit must be positive")
        now = self._now()
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            existing = conn.execute(
                "SELECT 1 FROM social_actions WHERE post_id = ?", (cleaned,)
            ).fetchone()
            daily_count = conn.execute(
                "SELECT COUNT(*) FROM social_actions WHERE substr(attempted_at, 1, 10) = ?",
                (now.date().isoformat(),),
            ).fetchone()[0]
            if existing or daily_count >= daily_limit:
                conn.execute("COMMIT")
                return False
            conn.execute(
                "INSERT INTO social_actions(post_id, attempted_at) VALUES (?, ?)",
                (cleaned, now.isoformat()),
            )
            conn.execute("COMMIT")
        return True

    def record_outcome(self, post_id: str, status: str, detail: str = "") -> None:
        if status not in {"published", "failed", "skipped"}:
            raise ValueError("unsupported social action status")
        safe_detail = str(detail)[:240]
        with self._connect() as conn:
            conn.execute(
                "UPDATE social_actions SET status = ?, detail = ? WHERE post_id = ?",
                (status, safe_detail, post_id),
            )

    def recent_actions(self, limit: int = 20) -> list[dict[str, str]]:
        if not 1 <= limit <= 100:
            raise ValueError("limit must be between 1 and 100")
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT post_id, attempted_at, status, detail FROM social_actions "
                "ORDER BY attempted_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [
            {"post_id": row[0], "attempted_at": row[1], "status": row[2], "detail": row[3]}
            for row in rows
        ]
