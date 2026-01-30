import builtins
import importlib
import sys

from tactus.core.message_history_manager import MessageHistoryManager
from tactus.primitives import session as session_module
from tactus.primitives.session import SessionPrimitive


class BrokenMessage:
    def __getattr__(self, _name):
        raise RuntimeError("boom")


def test_append_noop_without_manager():
    session = SessionPrimitive(session_manager=None, agent_name="agent")
    session.append({"role": "user", "content": "hi"})
    session.clear()
    assert session.history() == []


def test_append_noop_without_agent():
    session = SessionPrimitive(session_manager=MessageHistoryManager(), agent_name=None)
    session.append({"role": "user", "content": "hi"})
    session.clear()
    assert session.history() == []


def test_append_and_history_with_manager():
    manager = MessageHistoryManager()
    session = SessionPrimitive(session_manager=manager, agent_name="agent")
    session.append({"role": "user", "content": "hi"})
    session.inject_system("sys")

    history = session.history()
    assert history[0]["role"] == "user"
    assert history[1]["role"] == "system"


def test_clear_history():
    manager = MessageHistoryManager()
    session = SessionPrimitive(session_manager=manager, agent_name="agent")
    session.append({"role": "user", "content": "hi"})
    session.clear()
    assert session.history() == []


def test_history_fallback_for_non_dict_message():
    manager = MessageHistoryManager()
    session = SessionPrimitive(session_manager=manager, agent_name="agent")
    manager.histories["agent"] = [BrokenMessage()]

    history = session.history()
    assert history[0]["role"] == "unknown"


def test_load_and_save_are_noops():
    session = SessionPrimitive(session_manager=None, agent_name=None)
    session.load_from_node({"id": "node"})
    session.save_to_node({"id": "node"})


def test_session_fallback_import(monkeypatch):
    monkeypatch.delitem(sys.modules, "pydantic_ai.messages", raising=False)
    original_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "pydantic_ai.messages":
            raise ImportError("missing")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    reloaded = importlib.reload(session_module)
    assert reloaded.ModelMessage is dict

    monkeypatch.setattr(builtins, "__import__", original_import)
    importlib.reload(reloaded)
