"""Persistent, conservative state for autonomous Moltbook engagement."""

from __future__ import annotations

import hashlib
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path


class SocialState:
    """Record social attempts so restarts cannot cause duplicate engagement."""

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
            conn.execute(
                """CREATE TABLE IF NOT EXISTS social_publications (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    attempted_at TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'reserved',
                    title TEXT NOT NULL,
                    content_hash TEXT NOT NULL,
                    detail TEXT NOT NULL DEFAULT ''
                )"""
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_social_publications_attempted_at "
                "ON social_publications(attempted_at)"
            )

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path, timeout=10, isolation_level=None)

    @staticmethod
    def _now() -> datetime:
        return datetime.now(UTC)

    def reserve_comment(self, post_id: str, daily_limit: int = 5) -> bool:
        """Atomically reserve one post and enforce a UTC daily comment-attempt limit."""
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
        with self._connect() as conn:
            conn.execute(
                "UPDATE social_actions SET status = ?, detail = ? WHERE post_id = ?",
                (status, str(detail)[:240], post_id),
            )

    def reserve_publication(
        self, title: str, content: str, cooldown_hours: int = 24
    ) -> int | None:
        """Reserve one original post, enforcing a rolling cooldown and deduplication."""
        if not 1 <= len(title.strip()) <= 160 or not content.strip():
            return None
        if cooldown_hours < 1:
            raise ValueError("cooldown_hours must be positive")
        normalized = f"{title.strip().casefold()}\n{content.strip().casefold()}"
        content_hash = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
        now = self._now()
        cutoff = (now - timedelta(hours=cooldown_hours)).isoformat()
        duplicate_cutoff = (now - timedelta(days=30)).isoformat()
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            recent = conn.execute(
                "SELECT 1 FROM social_publications WHERE attempted_at >= ? "
                "AND status IN ('reserved', 'published', 'failed') LIMIT 1",
                (cutoff,),
            ).fetchone()
            duplicate = conn.execute(
                "SELECT 1 FROM social_publications WHERE attempted_at >= ? "
                "AND content_hash = ? LIMIT 1",
                (duplicate_cutoff, content_hash),
            ).fetchone()
            if recent or duplicate:
                conn.execute("COMMIT")
                return None
            cursor = conn.execute(
                "INSERT INTO social_publications(attempted_at, title, content_hash) "
                "VALUES (?, ?, ?)",
                (now.isoformat(), title.strip(), content_hash),
            )
            publication_id = int(cursor.lastrowid)
            conn.execute("COMMIT")
        return publication_id

    def record_publication_outcome(
        self, publication_id: int, status: str, detail: str = ""
    ) -> None:
        if status not in {"published", "failed", "skipped"}:
            raise ValueError("unsupported publication status")
        with self._connect() as conn:
            conn.execute(
                "UPDATE social_publications SET status = ?, detail = ? WHERE id = ?",
                (status, str(detail)[:240], publication_id),
            )

    def summary(self) -> dict[str, dict[str, int]]:
        """Return persistent counts for comment and original-post outcomes."""
        summary: dict[str, dict[str, int]] = {}
        with self._connect() as conn:
            for action_type, table in (("comments", "social_actions"), ("posts", "social_publications")):
                rows = conn.execute(
                    f"SELECT status, COUNT(*) FROM {table} GROUP BY status"
                ).fetchall()
                counts = {status: int(count) for status, count in rows}
                summary[action_type] = {
                    "attempts": sum(counts.values()),
                    "published": counts.get("published", 0),
                    "failed": counts.get("failed", 0),
                    "skipped": counts.get("skipped", 0),
                    "pending": counts.get("reserved", 0),
                }
        return summary

    def recent_actions(self, limit: int = 20) -> list[dict[str, str]]:
        if not 1 <= limit <= 100:
            raise ValueError("limit must be between 1 and 100")
        with self._connect() as conn:
            comments = conn.execute(
                "SELECT post_id, attempted_at, status, detail FROM social_actions"
            ).fetchall()
            publications = conn.execute(
                "SELECT title, attempted_at, status, detail FROM social_publications"
            ).fetchall()
        actions = [
            {
                "post_id": row[0],
                "attempted_at": row[1],
                "status": row[2],
                "detail": row[3],
                "action_type": "comment",
            }
            for row in comments
        ]
        actions.extend(
            {
                "post_id": f"new post: {row[0]}",
                "attempted_at": row[1],
                "status": row[2],
                "detail": row[3],
                "action_type": "post",
            }
            for row in publications
        )
        actions.sort(key=lambda item: item["attempted_at"], reverse=True)
        return actions[:limit]
