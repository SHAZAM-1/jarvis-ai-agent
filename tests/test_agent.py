from jarvis.agent import JarvisAgent
from jarvis.memory import MemoryStore
from jarvis.project_guardian import ProjectGuardian


class FakeLLM:
    def __init__(self):
        self.messages = None

    def chat(self, messages):
        self.messages = messages
        return "A helpful answer"


def test_agent_includes_user_approved_lessons_and_saves_reply(tmp_path):
    memory = MemoryStore(tmp_path / "memory.sqlite3")
    memory.add_lesson("The user prefers answers in Moroccan Darija.")
    llm = FakeLLM()
    agent = JarvisAgent(llm, memory)

    assert agent.reply("Explain this simply") == "A helpful answer"

    assert llm.messages is not None
    system_messages = [m["content"] for m in llm.messages if m["role"] == "system"]
    assert any("Moroccan Darija" in content for content in system_messages)
    assert memory.recent_messages() == [
        {"role": "user", "content": "Explain this simply"},
        {"role": "assistant", "content": "A helpful answer"},
    ]


def test_agent_rejects_blank_input_without_saving_it(tmp_path):
    memory = MemoryStore(tmp_path / "memory.sqlite3")
    agent = JarvisAgent(FakeLLM(), memory)

    try:
        agent.reply("   ")
    except ValueError as exc:
        assert str(exc) == "Please enter a message."
    else:
        raise AssertionError("Expected blank input to be rejected")

    assert memory.recent_messages() == []


def test_agent_receives_recent_project_guardian_evaluations(tmp_path):
    memory = MemoryStore(tmp_path / "memory.sqlite3")
    guardian = ProjectGuardian(FakeLLM(), tmp_path / "memory.sqlite3")
    guardian.record_outcome(
        "github_ci",
        "A prior project patch",
        "failed",
        "The Python 3.12 test job failed; do not repeat the unverified change.",
    )
    llm = FakeLLM()
    agent = JarvisAgent(llm, memory, guardian=guardian)

    assert agent.reply("What should I consider before changing the project?") == "A helpful answer"

    system_messages = [m["content"] for m in llm.messages if m["role"] == "system"]
    assert any("Project Guardian" in content for content in system_messages)
    assert any("A prior project patch" in content for content in system_messages)
    assert any("failed" in content for content in system_messages)
