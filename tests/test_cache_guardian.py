from __future__ import annotations

import os
import time

from jarvis.cache_guardian import CacheGuardian


def _age_tree(path, days: int = 30) -> None:
    stamp = time.time() - days * 86400
    for current, dirs, files in os.walk(path):
        for name in files:
            os.utime(os.path.join(current, name), (stamp, stamp))
        os.utime(current, (stamp, stamp))


def test_scan_only_lists_old_allowlisted_project_caches(tmp_path):
    old_cache = tmp_path / "src" / "__pycache__"
    old_cache.mkdir(parents=True)
    (old_cache / "module.cpython-311.pyc").write_bytes(b"compiled-cache")
    _age_tree(old_cache)

    recent_cache = tmp_path / ".pytest_cache"
    recent_cache.mkdir()
    (recent_cache / "lastfailed").write_text("recent", encoding="utf-8")

    protected = tmp_path / "data"
    protected.mkdir()
    (protected / "memory.sqlite3").write_text("keep", encoding="utf-8")
    old_cache_db = tmp_path / "memory.sqlite3"
    old_cache_db.write_text("keep", encoding="utf-8")
    os.utime(old_cache_db, (time.time() - 30 * 86400,) * 2)

    report = CacheGuardian(tmp_path).scan()

    assert [item.path for item in report.candidates] == ["src/__pycache__"]
    assert report.total_bytes == len(b"compiled-cache")
    assert report.min_age_days == 14


def test_cleanup_requires_matching_report_and_removes_only_listed_cache(tmp_path):
    cache = tmp_path / ".ruff_cache"
    cache.mkdir()
    (cache / "cache.db").write_bytes(b"old cache")
    _age_tree(cache)

    important = tmp_path / "project.sqlite3"
    important.write_text("must remain", encoding="utf-8")
    report = CacheGuardian(tmp_path).scan()

    removed = CacheGuardian(tmp_path).clean(report)

    assert removed == (".ruff_cache",)
    assert not cache.exists()
    assert important.read_text(encoding="utf-8") == "must remain"


def test_scan_skips_symlinked_cache_trees(tmp_path):
    outside = tmp_path.parent / f"{tmp_path.name}-outside"
    outside.mkdir()
    (outside / "important.txt").write_text("keep", encoding="utf-8")
    link = tmp_path / "__pycache__"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except (OSError, NotImplementedError):
        return

    report = CacheGuardian(tmp_path).scan()

    assert not report.candidates
    assert (outside / "important.txt").exists()


def test_cleanup_rejects_report_for_another_root(tmp_path):
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()
    cache = first / ".pytest_cache"
    cache.mkdir()
    (cache / "nodeids").write_text("[]", encoding="utf-8")
    _age_tree(cache)

    report = CacheGuardian(first).scan()

    try:
        CacheGuardian(second).clean(report)
    except ValueError as exc:
        assert "different project root" in str(exc)
    else:
        raise AssertionError("A report for another root must be rejected")
