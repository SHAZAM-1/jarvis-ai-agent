"""Conservative, project-scoped cache cleanup with a dry-run-first safety model.

Only old, known disposable development caches inside the project root are eligible.
This module never scans or deletes OS, user, model, Docker, virtual-environment, Git,
database, log, memory, credential, or arbitrary temporary files.
"""
from __future__ import annotations

import os
import shutil
import time
from dataclasses import dataclass
from pathlib import Path

_CACHE_DIR_NAMES = {
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
    ".hypothesis",
}
_CACHE_FILE_NAMES = {".coverage"}
_CACHE_FILE_PREFIXES = (".coverage.",)
_PROTECTED_PARTS = {
    ".git", ".venv", "venv", "env", "node_modules", "data", "logs", "log",
    "memory", "models", "ollama", "docker", "backups", "backup", "diagnostics",
    "secrets", "credentials",
}
DEFAULT_MIN_AGE_DAYS = 14
MAX_CANDIDATES = 200


@dataclass(frozen=True, slots=True)
class CacheCandidate:
    path: str
    kind: str
    size_bytes: int
    newest_mtime: float


@dataclass(frozen=True, slots=True)
class CleanupReport:
    root: str
    candidates: tuple[CacheCandidate, ...]
    total_bytes: int
    min_age_days: int

    @property
    def count(self) -> int:
        return len(self.candidates)


class CacheGuardian:
    """Plan and optionally remove only allow-listed, stale project cache artifacts."""

    def __init__(self, project_root: str | Path, *, min_age_days: int = DEFAULT_MIN_AGE_DAYS) -> None:
        self.root = Path(project_root).resolve()
        if not self.root.is_dir():
            raise ValueError("Project root must be an existing directory.")
        if min_age_days < 1:
            raise ValueError("min_age_days must be at least 1.")
        self.min_age_days = min_age_days

    def _protected(self, path: Path) -> bool:
        try:
            relative = path.relative_to(self.root)
        except ValueError:
            return True
        return any(part.lower() in _PROTECTED_PARTS for part in relative.parts)

    @staticmethod
    def _tree_stats(path: Path) -> tuple[int, float] | None:
        """Return size/newest mtime only for a plain tree with no symlinks."""
        size = 0
        newest = 0.0
        try:
            for current, dirs, files in os.walk(path, topdown=True, followlinks=False):
                current_path = Path(current)
                if current_path.is_symlink():
                    return None
                for name in list(dirs):
                    child = current_path / name
                    if child.is_symlink():
                        return None
                for name in files:
                    child = current_path / name
                    if child.is_symlink() or not child.is_file():
                        return None
                    stat = child.stat(follow_symlinks=False)
                    size += stat.st_size
                    newest = max(newest, stat.st_mtime)
                newest = max(newest, current_path.stat(follow_symlinks=False).st_mtime)
        except OSError:
            return None
        return size, newest

    def scan(self, *, now: float | None = None) -> CleanupReport:
        cutoff = (time.time() if now is None else now) - self.min_age_days * 86400
        candidates: list[CacheCandidate] = []
        for current, dirs, files in os.walk(self.root, topdown=True, followlinks=False):
            base = Path(current)
            dirs[:] = sorted(
                name for name in dirs
                if name.lower() not in _PROTECTED_PARTS
                and not (base / name).is_symlink()
                and name not in _CACHE_DIR_NAMES
            )
            if self._protected(base):
                dirs[:] = []
                continue

            # Known cache directories are treated as a single candidate only if stale,
            # entirely inside the project, and free of symlinks.
            for name in sorted(set(os.listdir(base)) & _CACHE_DIR_NAMES):
                path = base / name
                if path.is_symlink() or not path.is_dir() or self._protected(path):
                    continue
                stats = self._tree_stats(path)
                if stats is None:
                    continue
                size, newest = stats
                if newest and newest <= cutoff:
                    candidates.append(CacheCandidate(path.relative_to(self.root).as_posix(), "cache directory", size, newest))
            for name in files:
                path = base / name
                if path.is_symlink() or not path.is_file() or self._protected(path):
                    continue
                if name not in _CACHE_FILE_NAMES and not name.startswith(_CACHE_FILE_PREFIXES):
                    continue
                try:
                    stat = path.stat(follow_symlinks=False)
                except OSError:
                    continue
                if stat.st_mtime <= cutoff:
                    candidates.append(CacheCandidate(path.relative_to(self.root).as_posix(), "coverage cache", stat.st_size, stat.st_mtime))
            if len(candidates) >= MAX_CANDIDATES:
                break

        candidates.sort(key=lambda item: item.path)
        candidates = candidates[:MAX_CANDIDATES]
        return CleanupReport(str(self.root), tuple(candidates), sum(c.size_bytes for c in candidates), self.min_age_days)

    def clean(self, report: CleanupReport) -> tuple[str, ...]:
        """Remove exactly the previously listed eligible paths; never follows symlinks."""
        if Path(report.root).resolve() != self.root:
            raise ValueError("Cleanup report belongs to a different project root.")
        removed: list[str] = []
        for candidate in report.candidates:
            relative = Path(candidate.path)
            if relative.is_absolute() or ".." in relative.parts:
                continue
            target = self.root / relative
            try:
                resolved_parent = target.parent.resolve(strict=True)
                if not resolved_parent.is_relative_to(self.root) or target.is_symlink():
                    continue
                if candidate.kind == "cache directory":
                    if target.name not in _CACHE_DIR_NAMES or not target.is_dir():
                        continue
                    # Recheck freshness immediately before deletion.
                    stats = self._tree_stats(target)
                    cutoff = time.time() - self.min_age_days * 86400
                    # Abort if the tree changed after the preview; never clean newly added content.
                    if (
                        stats is None
                        or stats != (candidate.size_bytes, candidate.newest_mtime)
                        or (stats[1] and stats[1] > cutoff)
                    ):
                        continue
                    shutil.rmtree(target)
                elif candidate.kind == "coverage cache":
                    if target.name not in _CACHE_FILE_NAMES and not target.name.startswith(_CACHE_FILE_PREFIXES):
                        continue
                    if not target.is_file():
                        continue
                    current_stat = target.stat(follow_symlinks=False)
                    if (
                        current_stat.st_size != candidate.size_bytes
                        or current_stat.st_mtime != candidate.newest_mtime
                        or current_stat.st_mtime > time.time() - self.min_age_days * 86400
                    ):
                        continue
                    target.unlink()
                else:
                    continue
                removed.append(candidate.path)
            except OSError:
                continue
        return tuple(removed)
