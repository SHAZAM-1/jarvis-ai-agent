from __future__ import annotations

import json

import pytest

from jarvis.reviewer_auth import ReviewerAuthenticator


def test_provision_stores_salted_hash_not_plaintext(tmp_path):
    path = tmp_path / "reviewer.json"
    auth = ReviewerAuthenticator(path)
    auth.provision("local-reviewer", "correct horse battery staple")

    stored = json.loads(path.read_text(encoding="utf-8"))
    assert stored["reviewer_id"] == "local-reviewer"
    assert stored["kdf"] == "scrypt-n16384-r8-p1"
    assert len(bytes.fromhex(stored["salt"])) == 16
    assert len(bytes.fromhex(stored["digest"])) == 32
    assert "correct horse battery staple" not in path.read_text(encoding="utf-8")
    assert auth.authenticate("correct horse battery staple") == "local-reviewer"
    assert auth.authenticate("wrong passphrase value") is None
    assert auth.authenticate("x" * 1025) is None


def test_provision_requires_long_passphrase_and_never_overwrites(tmp_path):
    auth = ReviewerAuthenticator(tmp_path / "reviewer.json")
    with pytest.raises(ValueError, match="12 characters"):
        auth.provision("reviewer", "short")
    auth.provision("reviewer", "a sufficiently long test passphrase")
    with pytest.raises(FileExistsError):
        auth.provision("different", "another sufficiently long passphrase")


def test_missing_malformed_and_unsupported_credentials_fail_closed(tmp_path):
    path = tmp_path / "reviewer.json"
    auth = ReviewerAuthenticator(path)
    assert auth.authenticate("anything sufficiently long") is None
    path.write_text("{malformed", encoding="utf-8")
    assert not auth.is_configured()
    assert auth.authenticate("anything sufficiently long") is None
    path.write_text(json.dumps({
        "version": 1, "reviewer_id": "spoof", "kdf": "fast-sha256",
        "salt": "00" * 16, "digest": "00" * 32,
    }), encoding="utf-8")
    assert auth.authenticate("anything sufficiently long") is None


def test_rotation_and_revocation_require_current_passphrase(tmp_path):
    auth = ReviewerAuthenticator(tmp_path / "reviewer.json")
    auth.provision("local-reviewer", "first passphrase sufficiently long")
    with pytest.raises(PermissionError):
        auth.rotate("wrong passphrase sufficiently long", "second passphrase sufficiently long")
    auth.rotate("first passphrase sufficiently long", "second passphrase sufficiently long")
    assert auth.authenticate("first passphrase sufficiently long") is None
    assert auth.authenticate("second passphrase sufficiently long") == "local-reviewer"
    with pytest.raises(PermissionError):
        auth.revoke("wrong passphrase sufficiently long")
    auth.revoke("second passphrase sufficiently long")
    assert not auth.is_configured()


def test_reviewer_cli_terminal_gate_rejects_noninteractive_input(monkeypatch):
    import io
    import sys

    from jarvis.cli import _reviewer_terminal_available

    monkeypatch.setattr(sys, "stdin", io.StringIO("not a terminal"))
    monkeypatch.setattr(sys, "stderr", io.StringIO())
    assert _reviewer_terminal_available() is False
