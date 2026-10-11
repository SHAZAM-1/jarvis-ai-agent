from __future__ import annotations

from jarvis.owner_policy import OWNER_TRUST_POLICY, PROTECTED_PATHS, PROJECT_SCOPE
from jarvis.self_development import (
    SelfDevelopmentState,
    is_allowed_path,
    redact_source,
    validate_patch,
)


def test_owner_policy_keeps_creator_trust_and_project_scope_explicit():
    assert "owner" in OWNER_TRUST_POLICY.lower()
    assert "Jarvis AI Agent" in PROJECT_SCOPE
    assert "src/jarvis/self_development.py" in PROTECTED_PATHS


def test_allowed_paths_include_project_code_tests_and_docs_only():
    assert is_allowed_path("src/jarvis/moltbook_loop.py")
    assert is_allowed_path("tests/test_agent.py")
    assert is_allowed_path("docs/roadmap.md")
    assert is_allowed_path("README.md")
    assert not is_allowed_path("src/jarvis/agent.py")
    assert not is_allowed_path("src/jarvis/self_development.py")
    assert not is_allowed_path("pyproject.toml")
    assert not is_allowed_path(".github/workflows/tests.yml")
    assert not is_allowed_path("../outside.py")
    assert not is_allowed_path(".env")


def test_patch_validator_accepts_small_in_scope_change():
    patch = (
        "diff --git a/src/jarvis/moltbook_loop.py b/src/jarvis/moltbook_loop.py\n"
        "--- a/src/jarvis/moltbook_loop.py\n"
        "+++ b/src/jarvis/moltbook_loop.py\n"
        "@@ -1,1 +1,2 @@\n"
        " existing = True\n"
        "+new_value = 'Jarvis project improvement'\n"
    )
    valid, reason, paths = validate_patch(patch)
    assert valid, reason
    assert paths == ["src/jarvis/moltbook_loop.py"]


def test_patch_validator_rejects_protected_paths_and_execution_primitives():
    protected = (
        "diff --git a/src/jarvis/cli.py b/src/jarvis/cli.py\n"
        "--- a/src/jarvis/cli.py\n+++ b/src/jarvis/cli.py\n"
        "@@ -1 +1,2 @@\n old = 1\n+new = 2\n"
    )
    assert not validate_patch(protected)[0]
    dangerous = (
        "diff --git a/src/jarvis/moltbook_loop.py b/src/jarvis/moltbook_loop.py\n"
        "--- a/src/jarvis/moltbook_loop.py\n+++ b/src/jarvis/moltbook_loop.py\n"
        "@@ -1 +1,2 @@\n old = 1\n+subprocess.run(['rm', '-rf', '/'])\n"
    )
    assert not validate_patch(dangerous)[0]


def test_patch_validator_rejects_deletions_symlinks_and_oversized_diffs():
    deletion = (
        "diff --git a/src/jarvis/moltbook_loop.py b/src/jarvis/moltbook_loop.py\n"
        "deleted file mode 100644\n--- a/src/jarvis/moltbook_loop.py\n+++ /dev/null\n"
    )
    symlink = (
        "diff --git a/src/jarvis/moltbook_loop.py b/src/jarvis/moltbook_loop.py\n"
        "new file mode 120000\n--- /dev/null\n+++ b/src/jarvis/moltbook_loop.py\n+x\n"
    )
    assert not validate_patch(deletion)[0]
    assert not validate_patch(symlink)[0]
    assert not validate_patch("x" * 50_001)[0]


def test_redact_source_masks_credential_like_values():
    source = 'MOLTBOOK_API_KEY = "secret-value-123"\nAuthorization: Bearer abcdefghijklmnop'
    redacted = redact_source(source)
    assert "secret-value-123" not in redacted
    assert "abcdefghijklmnop" not in redacted


def test_self_development_state_enforces_24_hour_cooldown(tmp_path):
    state = SelfDevelopmentState(tmp_path / "jarvis.db")
    run_id = state.reserve(cooldown_hours=24)
    assert run_id is not None
    assert state.reserve(cooldown_hours=24) is None
    state.finish(run_id, "no_change", "No patch")
