from types import SimpleNamespace

import pytest

from tactus.ide.coding_assistant import CodingAssistantAgent
import tactus.ide.coding_assistant as coding_assistant


class FakeAgent:
    def __call__(self, chat_history, user_message, workspace_root):
        return SimpleNamespace(response="ok", tool_calls=[{"name": "noop"}])


def test_openai_requires_api_key(monkeypatch, tmp_path):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(ValueError, match="OpenAI API key not found"):
        CodingAssistantAgent(str(tmp_path), {"coding_assistant": {"provider": "openai"}})


def test_setup_openai_configures_dspy(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENAI_API_KEY", "key")

    configured = {}

    def fake_configure(lm=None):
        configured["lm"] = lm

    monkeypatch.setattr(
        coding_assistant.dspy, "OpenAI", lambda **kwargs: {"lm": kwargs}, raising=False
    )
    monkeypatch.setattr(
        coding_assistant.dspy, "settings", SimpleNamespace(configure=fake_configure)
    )
    monkeypatch.setattr(CodingAssistantAgent, "_create_agent", lambda self: "agent")

    agent = CodingAssistantAgent(str(tmp_path), {"coding_assistant": {"provider": "openai"}})
    assert agent.agent == "agent"
    assert "lm" in configured


def test_setup_anthropic_configures_dspy(monkeypatch, tmp_path):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "key")

    monkeypatch.setattr(
        coding_assistant.dspy, "Claude", lambda **kwargs: {"lm": kwargs}, raising=False
    )
    monkeypatch.setattr(
        coding_assistant.dspy, "settings", SimpleNamespace(configure=lambda lm=None: None)
    )
    monkeypatch.setattr(CodingAssistantAgent, "_create_agent", lambda self: "agent")

    agent = CodingAssistantAgent(
        str(tmp_path), {"coding_assistant": {"provider": "anthropic", "model": "claude"}}
    )
    assert agent.agent == "agent"


def test_anthropic_requires_api_key(monkeypatch, tmp_path):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(ValueError, match="Anthropic API key not found"):
        CodingAssistantAgent(
            str(tmp_path), {"coding_assistant": {"provider": "anthropic", "model": "claude"}}
        )


def test_setup_rejects_unknown_provider(monkeypatch, tmp_path):
    monkeypatch.setattr(
        coding_assistant.dspy, "settings", SimpleNamespace(configure=lambda lm=None: None)
    )
    with pytest.raises(ValueError, match="Unsupported provider"):
        CodingAssistantAgent(str(tmp_path), {"coding_assistant": {"provider": "other"}})


def test_process_message_and_history(monkeypatch, tmp_path):
    monkeypatch.setattr(CodingAssistantAgent, "_setup_dspy", lambda self: None)
    agent = CodingAssistantAgent(str(tmp_path))
    agent.agent = FakeAgent()

    result = agent.process_message("hello")
    assert result["response"] == "ok"
    assert agent.messages[0]["role"] == "user"
    assert agent.messages[1]["role"] == "assistant"

    history = agent._format_chat_history()
    assert "User: hello" in history


def test_process_message_handles_agent_error(monkeypatch, tmp_path):
    monkeypatch.setattr(CodingAssistantAgent, "_setup_dspy", lambda self: None)
    agent = CodingAssistantAgent(str(tmp_path))

    class BoomAgent:
        def __call__(self, **_kwargs):
            raise RuntimeError("boom")

    agent.agent = BoomAgent()

    result = agent.process_message("hello")
    assert "I encountered an error" in result["response"]
    assert result["tool_calls"] == []
    assert agent.messages[-1]["role"] == "assistant"


def test_file_tools_and_reset(tmp_path, monkeypatch):
    monkeypatch.setattr(CodingAssistantAgent, "_setup_dspy", lambda self: None)
    agent = CodingAssistantAgent(str(tmp_path))

    assert agent.file_exists("missing.txt") is False
    assert "Successfully wrote" in agent.write_file("a.txt", "hi")
    assert agent.file_exists("a.txt") is True
    assert agent.read_file("a.txt") == "hi"
    listing = agent.list_directory(".")
    assert "a.txt" in listing

    agent.messages.append({"role": "user", "content": "x"})
    agent.reset_conversation()
    assert agent.messages == []


def test_execution_context_wait_for_human(tmp_path, monkeypatch):
    from pydantic import ValidationError

    monkeypatch.setattr(CodingAssistantAgent, "_setup_dspy", lambda self: None)
    agent = CodingAssistantAgent(str(tmp_path))

    with pytest.raises(ValidationError):
        agent.execution_context.wait_for_human(
            request_type="input",
            message="Need input",
            default_value="default",
            metadata={"source": "test"},
        )


def test_format_chat_history_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(CodingAssistantAgent, "_setup_dspy", lambda self: None)
    agent = CodingAssistantAgent(str(tmp_path))

    assert agent._format_chat_history() == "No previous messages."


def test_list_directory_paths(tmp_path, monkeypatch):
    monkeypatch.setattr(CodingAssistantAgent, "_setup_dspy", lambda self: None)
    agent = CodingAssistantAgent(str(tmp_path))

    missing = agent.list_directory("missing")
    assert "Directory not found" in missing

    agent.write_file("file.txt", "hi")
    not_dir = agent.list_directory("file.txt")
    assert "Not a directory" in not_dir

    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()
    empty_listing = agent.list_directory("empty")
    assert "Directory is empty" in empty_listing


def test_list_directory_includes_subdir(tmp_path, monkeypatch):
    monkeypatch.setattr(CodingAssistantAgent, "_setup_dspy", lambda self: None)
    agent = CodingAssistantAgent(str(tmp_path))

    subdir = tmp_path / "subdir"
    subdir.mkdir()
    agent.write_file("subdir/file.txt", "hi")

    root_listing = agent.list_directory(".")
    assert "subdir/" in root_listing

    listing = agent.list_directory("subdir")
    assert "file.txt" in listing


def test_list_directory_handles_exception(tmp_path, monkeypatch):
    monkeypatch.setattr(CodingAssistantAgent, "_setup_dspy", lambda self: None)
    agent = CodingAssistantAgent(str(tmp_path))

    def boom_resolve(_path):
        raise RuntimeError("explode")

    agent.file_primitive._resolve_path = boom_resolve

    listing = agent.list_directory(".")
    assert "Error listing directory" in listing


def test_file_tools_error_paths(tmp_path, monkeypatch):
    monkeypatch.setattr(CodingAssistantAgent, "_setup_dspy", lambda self: None)
    agent = CodingAssistantAgent(str(tmp_path))

    def boom_read(_path):
        raise RuntimeError("read-fail")

    def boom_write(_path, _content):
        raise RuntimeError("write-fail")

    def boom_exists(_path):
        raise RuntimeError("exists-fail")

    agent.file_primitive.read = boom_read
    agent.file_primitive.write = boom_write
    agent.file_primitive.exists = boom_exists

    assert "Error reading file" in agent.read_file("missing.txt")
    assert "Error writing file" in agent.write_file("missing.txt", "x")
    assert agent.file_exists("missing.txt") is False


def test_get_available_tools_structure(tmp_path, monkeypatch):
    monkeypatch.setattr(CodingAssistantAgent, "_setup_dspy", lambda self: None)
    agent = CodingAssistantAgent(str(tmp_path))
    tools = agent.get_available_tools()
    names = {tool["name"] for tool in tools}
    assert {"read_file", "write_file", "list_directory", "file_exists"} <= names


def test_create_agent_builds_signature(tmp_path, monkeypatch):
    monkeypatch.setattr(CodingAssistantAgent, "_setup_dspy", lambda self: None)
    agent = CodingAssistantAgent(str(tmp_path))

    captured = {}

    def fake_chain(signature):
        captured["signature"] = signature
        return "agent"

    monkeypatch.setattr(coding_assistant.dspy, "ChainOfThought", fake_chain)

    result = agent._create_agent()

    assert result == "agent"
    signature = captured["signature"]
    fields = getattr(signature, "model_fields", {})
    assert "chat_history" in fields
    assert "user_message" in fields
    assert "workspace_root" in fields
