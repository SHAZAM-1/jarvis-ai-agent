from __future__ import annotations

import json

from jarvis.project_guardian import ProjectGuardian


class FakeLLM:
    base_url = "http://127.0.0.1:11434"

    def __init__(self, *responses: str, available: bool = True) -> None:
        self.responses = list(responses)
        self.available = available
        self.calls = 0
        self.messages = []

    def is_available(self) -> bool:
        return self.available

    def chat(self, messages):
        self.calls += 1
        self.messages.append(messages)
        if not self.responses:
            return "not-json"
        return self.responses.pop(0)


def _approved(score: int = 94) -> str:
    return json.dumps(
        {
            "score": score,
            "verdict": "approve",
            "reason": "Small, evidence-backed, in-scope change with tests.",
            "risks": [],
            "lesson": "Keep changes small and verify them.",
        }
    )


def _patch(path: str = "src/jarvis/example.py") -> str:
    return (
        f"diff --git a/{path} b/{path}\n"
        f"--- a/{path}\n"
        f"+++ b/{path}\n"
        "@@ -1 +1,2 @@\n"
        " value = 1\n"
        "+value = 2\n"
    )


def test_guardian_approves_only_after_policy_gate_and_records_context(tmp_path):
    llm = FakeLLM(_approved())
    guardian = ProjectGuardian(llm, tmp_path / "jarvis.sqlite3")

    decision = guardian.evaluate_change("Improve a small helper", _patch())

    assert decision.approved
    assert decision.score == 94
    assert decision.event_id is not None
    assert "Improve a small helper" in guardian.context_summary()
    assert "Keep changes small and verify them." in guardian.context_summary()
    assert llm.calls == 1


def test_guardian_blocks_protected_path_without_asking_model(tmp_path):
    llm = FakeLLM(_approved())
    guardian = ProjectGuardian(llm, tmp_path / "jarvis.sqlite3")

    decision = guardian.evaluate_change(
        "Try to change the Guardian", _patch("src/jarvis/project_guardian.py")
    )

    assert not decision.approved
    assert decision.score == 0
    assert "Protected or unsafe path blocked" in decision.reason
    assert llm.calls == 0
    assert "REJECT" in guardian.context_summary()


def test_guardian_fails_closed_on_invalid_model_response(tmp_path):
    guardian = ProjectGuardian(FakeLLM("not-json"), tmp_path / "jarvis.sqlite3")

    decision = guardian.evaluate_change("Change helper", _patch())

    assert not decision.approved
    assert decision.score == 0
    assert "fail-closed" in decision.reason
    assert "must stop autonomous development" in guardian.context_summary()


def test_guardian_rejects_score_below_threshold_even_if_model_approves(tmp_path):
    guardian = ProjectGuardian(FakeLLM(_approved(84)), tmp_path / "jarvis.sqlite3")

    decision = guardian.evaluate_change("Change helper", _patch())

    assert not decision.approved
    assert decision.score == 84
    assert "threshold 85" in decision.reason


def test_guardian_never_sends_source_to_nonlocal_endpoint(tmp_path):
    class RemoteLLM(FakeLLM):
        base_url = "https://remote.example"

        def is_available(self) -> bool:
            raise AssertionError("Remote model must never be contacted")

    guardian = ProjectGuardian(RemoteLLM(_approved()), tmp_path / "jarvis.sqlite3")
    decision = guardian.evaluate_change("Change helper", _patch())

    assert not decision.approved
    assert "not loopback-local" in decision.reason


def test_guardian_records_health_report_rating_and_objective_ci_outcome(tmp_path):
    llm = FakeLLM(_approved(), _approved())
    guardian = ProjectGuardian(llm, tmp_path / "jarvis.sqlite3")

    report = guardian.evaluate_report(
        "Tests passed; one documented risk remains.",
        evidence="pytest exit=0; no source changes made.",
    )
    ci = guardian.record_outcome("github_ci", "Improve helper", "passed")

    assert report.approved
    assert ci.approved
    context = guardian.context_summary()
    assert "health_report" in context
    assert "github_ci" in context
    assert "Improve helper" in context
    assert "passed" in context
