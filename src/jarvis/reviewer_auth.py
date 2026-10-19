"""Local reviewer-passphrase authentication for the single-owner CLI.

This verifies possession of a locally provisioned passphrase. It is not protection
against a process running as the same OS user or direct access to this file.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import stat
import tempfile
from pathlib import Path
from typing import Any

_SCRYPT_N = 1 << 14
_SCRYPT_R = 8
_SCRYPT_P = 1
_KEY_LENGTH = 32
_MIN_PASSPHRASE_LENGTH = 12
_MAX_PASSPHRASE_LENGTH = 1024


class ReviewerAuthenticator:
    """Provision and verify one local reviewer credential without storing plaintext."""

    def __init__(self, credential_path: str | Path) -> None:
        self.path = Path(credential_path).expanduser()

    @staticmethod
    def _derive(passphrase: str, salt: bytes) -> bytes:
        return hashlib.scrypt(
            passphrase.encode("utf-8"), salt=salt,
            n=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P, dklen=_KEY_LENGTH,
        )

    @staticmethod
    def _validate_passphrase(passphrase: str) -> None:
        if not isinstance(passphrase, str) or len(passphrase) < _MIN_PASSPHRASE_LENGTH:
            raise ValueError("Reviewer passphrase must contain at least 12 characters.")
        if len(passphrase) > _MAX_PASSPHRASE_LENGTH:
            raise ValueError("Reviewer passphrase must contain at most 1024 characters.")

    def _read_record(self) -> dict[str, Any] | None:
        try:
            if self.path.is_symlink() or not self.path.is_file():
                return None
            if os.name != "nt" and stat.S_IMODE(self.path.stat().st_mode) & 0o077:
                return None
            record = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(record, dict) or record.get("version") != 1:
                return None
            if record.get("kdf") != "scrypt-n16384-r8-p1":
                return None
            if not isinstance(record.get("reviewer_id"), str) or not record["reviewer_id"].strip():
                return None
            if not isinstance(record.get("salt"), str) or not isinstance(record.get("digest"), str):
                return None
            return record
        except (OSError, UnicodeError, json.JSONDecodeError):
            return None

    def is_configured(self) -> bool:
        return self._read_record() is not None

    @staticmethod
    def _restrict_permissions(path: Path) -> None:
        try:
            os.chmod(path, 0o600)
        except OSError:
            if os.name != "nt":
                raise
        if os.name != "nt" and stat.S_IMODE(path.stat().st_mode) & 0o077:
            raise PermissionError("Reviewer credential permissions are not owner-only.")

    def _create_exclusive(self, record: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        fd = os.open(self.path, flags, 0o600)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                json.dump(record, stream, sort_keys=True)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
        except Exception:
            try:
                self.path.unlink()
            except OSError:
                pass
            raise
        self._restrict_permissions(self.path)

    def provision(self, reviewer_id: str, passphrase: str) -> None:
        """Create a credential once; never silently replace an existing credential."""
        if self.path.exists() or self.path.is_symlink():
            raise FileExistsError("Reviewer credential already exists; authenticate to rotate it.")
        if not isinstance(reviewer_id, str) or not reviewer_id.strip() or len(reviewer_id.strip()) > 80:
            raise ValueError("Reviewer label must contain 1–80 non-empty characters.")
        self._validate_passphrase(passphrase)
        salt = secrets.token_bytes(16)
        record = {
            "version": 1,
            "reviewer_id": reviewer_id.strip(),
            "kdf": "scrypt-n16384-r8-p1",
            "salt": salt.hex(),
            "digest": self._derive(passphrase, salt).hex(),
        }
        self._create_exclusive(record)

    def authenticate(self, passphrase: str) -> str | None:
        record = self._read_record()
        if record is None or not isinstance(passphrase, str) or len(passphrase) > _MAX_PASSPHRASE_LENGTH:
            return None
        try:
            salt = bytes.fromhex(record["salt"])
            expected = bytes.fromhex(record["digest"])
            if len(salt) != 16 or len(expected) != _KEY_LENGTH:
                return None
            actual = self._derive(passphrase, salt)
        except (ValueError, TypeError, KeyError, MemoryError):
            return None
        return record["reviewer_id"] if hmac.compare_digest(actual, expected) else None

    def rotate(self, current_passphrase: str, new_passphrase: str) -> None:
        reviewer_id = self.authenticate(current_passphrase)
        if reviewer_id is None:
            raise PermissionError("Reviewer authentication failed.")
        self._validate_passphrase(new_passphrase)
        salt = secrets.token_bytes(16)
        record = {
            "version": 1,
            "reviewer_id": reviewer_id,
            "kdf": "scrypt-n16384-r8-p1",
            "salt": salt.hex(),
            "digest": self._derive(new_passphrase, salt).hex(),
        }
        if self.path.is_symlink() or not self.path.is_file():
            raise PermissionError("Reviewer credential file is unavailable or unsafe.")
        fd, temporary = tempfile.mkstemp(prefix=".jarvis-reviewer-", dir=self.path.parent)
        try:
            self._restrict_permissions(Path(temporary))
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                json.dump(record, stream, sort_keys=True)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.path)
            self._restrict_permissions(self.path)
        finally:
            try:
                os.unlink(temporary)
            except FileNotFoundError:
                pass

    def revoke(self, current_passphrase: str) -> None:
        if self.authenticate(current_passphrase) is None:
            raise PermissionError("Reviewer authentication failed.")
        if self.path.is_symlink() or not self.path.is_file():
            raise PermissionError("Reviewer credential file is unavailable or unsafe.")
        self.path.unlink()
