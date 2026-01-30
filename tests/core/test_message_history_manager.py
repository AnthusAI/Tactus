import builtins
import importlib
import sys

from tactus.core import message_history_manager as manager_module
from tactus.core.message_history_manager import MessageHistoryManager
from tactus.core.registry import MessageHistoryConfiguration


class FakeMessage:
    def __init__(self, role, content):
        self.role = role
        self.content = content


class BrokenMessage:
    def __getattr__(self, _name):
        raise RuntimeError("boom")


def _messages():
    return [
        {"role": "system", "content": "ssss"},
        {"role": "system", "content": "tttt"},
        {"role": "user", "content": "aaaa"},
        {"role": "assistant", "content": "bbbb"},
        {"role": "user", "content": "cccc"},
    ]


def test_filter_first_n():
    manager = MessageHistoryManager()
    messages = _messages()

    filtered = manager._apply_filter(messages, ("first_n", 3), None)

    assert len(filtered) == 3
    assert filtered[0]["role"] == "system"
    assert filtered[-1]["role"] == "user"


def test_filter_head_tokens():
    manager = MessageHistoryManager()
    messages = _messages()

    filtered = manager._apply_filter(messages, ("head_tokens", 2), None)

    assert len(filtered) == 2
    assert filtered[0]["content"] == "ssss"
    assert filtered[1]["content"] == "tttt"


def test_filter_head_tokens_all_messages_fit():
    manager = MessageHistoryManager()
    messages = _messages()

    filtered = manager._apply_filter(messages, ("head_tokens", 100), None)

    assert filtered == messages


def test_filter_head_tokens_zero_returns_empty():
    manager = MessageHistoryManager()
    messages = _messages()
    assert manager._apply_filter(messages, ("head_tokens", 0), None) == []


def test_filter_tail_tokens():
    manager = MessageHistoryManager()
    messages = _messages()

    filtered = manager._apply_filter(messages, ("tail_tokens", 2), None)

    assert len(filtered) == 2
    assert filtered[0]["content"] == "bbbb"
    assert filtered[1]["content"] == "cccc"


def test_filter_system_prefix():
    manager = MessageHistoryManager()
    messages = _messages()

    filtered = manager._apply_filter(messages, ("system_prefix", None), None)

    assert len(filtered) == 2
    assert all(msg["role"] == "system" for msg in filtered)


def test_filter_system_prefix_all_system_messages():
    manager = MessageHistoryManager()
    messages = [
        {"role": "system", "content": "a"},
        {"role": "system", "content": "b"},
    ]

    filtered = manager._apply_filter(messages, ("system_prefix", None), None)

    assert filtered == messages


def test_get_history_sources_and_filter_callable():
    manager = MessageHistoryManager()
    manager.add_message("agent_a", {"role": "user", "content": "a"})
    manager.add_message("agent_b", {"role": "user", "content": "b"})
    manager.add_message(None, {"role": "system", "content": "s"})

    config = MessageHistoryConfiguration(source="shared", filter=None)
    assert manager.get_history_for_agent("agent_a", config) == manager.shared_history

    config = MessageHistoryConfiguration(source="agent_b", filter=None)
    assert manager.get_history_for_agent("agent_a", config) == manager.histories["agent_b"]

    def only_users(messages, context):
        return [m for m in messages if m["role"] == "user"]

    config = MessageHistoryConfiguration(source="own", filter=only_users)
    result = manager.get_history_for_agent("agent_a", config, context={})
    assert len(result) == 1
    assert result[0]["role"] == "user"
    assert result[0]["content"] == "a"


def test_get_history_default_config():
    manager = MessageHistoryManager()
    manager.add_message("agent_a", {"role": "user", "content": "a"})
    assert manager.get_history_for_agent("agent_a") == manager.histories["agent_a"]


def test_filter_callable_failure_returns_unfiltered():
    manager = MessageHistoryManager()
    messages = _messages()

    def broken_filter(messages, context):
        raise ValueError("boom")

    filtered = manager._apply_filter(messages, broken_filter, None)

    assert filtered == messages


def test_filter_invalid_spec_returns_messages():
    manager = MessageHistoryManager()
    messages = _messages()
    filtered = manager._apply_filter(messages, ("last_n",), None)
    assert filtered == messages


def test_filter_unknown_returns_messages():
    manager = MessageHistoryManager()
    messages = _messages()
    filtered = manager._apply_filter(messages, ("mystery", 3), None)
    assert filtered == messages


def test_add_message_sets_metadata_and_shared():
    manager = MessageHistoryManager()

    manager.add_message("agent", {"role": "user", "content": "hi"}, also_shared=True)

    msg = manager.histories["agent"][0]
    assert msg["id"] == 1
    assert "created_at" in msg
    assert manager.shared_history[0]["id"] == 1


def test_add_message_non_dict_skips_metadata():
    manager = MessageHistoryManager()
    message = FakeMessage("user", "hi")

    manager.add_message("agent", message)

    assert manager.histories["agent"][0] is message


def test_clear_histories():
    manager = MessageHistoryManager()
    manager.add_message("agent", {"role": "user", "content": "hi"})
    manager.add_message(None, {"role": "system", "content": "s"})

    manager.clear_agent_history("agent")
    manager.clear_shared_history()

    assert manager.histories["agent"] == []
    assert manager.shared_history == []


def test_filter_last_n_and_first_n_zero():
    manager = MessageHistoryManager()
    messages = _messages()

    assert manager._apply_filter(messages, ("last_n", 0), None) == []
    assert manager._apply_filter(messages, ("first_n", 0), None) == []


def test_filter_by_token_budget_respects_content_lists():
    manager = MessageHistoryManager()
    messages = [
        {"role": "user", "content": [{"text": "aaaa"}, {"text": "bbbb"}]},
        {"role": "assistant", "content": "cccc"},
    ]

    filtered = manager._apply_filter(messages, ("token_budget", 2), None)

    assert filtered == [messages[1]]


def test_filter_by_token_budget_allows_all_messages():
    manager = MessageHistoryManager()
    messages = _messages()
    filtered = manager._apply_filter(messages, ("token_budget", 100), None)
    assert filtered == messages


def test_filter_by_token_budget_zero_returns_empty():
    manager = MessageHistoryManager()
    messages = _messages()
    assert manager._apply_filter(messages, ("token_budget", 0), None) == []


def test_filter_by_role_handles_object_messages():
    manager = MessageHistoryManager()
    messages = [
        {"role": "user", "content": "a"},
        FakeMessage("assistant", "b"),
    ]

    filtered = manager._apply_filter(messages, ("by_role", "assistant"), None)

    assert filtered == [messages[1]]


def test_filter_compose_applies_in_order():
    manager = MessageHistoryManager()
    messages = _messages()
    filtered = manager._apply_filter(
        messages,
        ("compose", [("first_n", 4), ("by_role", "user")]),
        None,
    )

    assert filtered == [
        {"role": "user", "content": "aaaa"},
    ]


def test_checkpoints_and_next_message_id():
    manager = MessageHistoryManager()
    assert manager.next_message_id() == 1

    manager.record_checkpoint("start", 5)
    assert manager.get_checkpoint("start") == 5


def test_estimate_message_chars_for_object():
    manager = MessageHistoryManager()
    message = FakeMessage("user", "abcd")

    assert manager._estimate_message_chars(message) == 4


def test_estimate_message_chars_for_content_list_parts():
    manager = MessageHistoryManager()
    message = {"role": "user", "content": [{"text": "aa"}, "bbb"]}
    assert manager._estimate_message_chars(message) == 5


def test_estimate_message_chars_for_non_string_content():
    manager = MessageHistoryManager()
    message = {"role": "user", "content": 123}
    assert manager._estimate_message_chars(message) == len("123")


def test_estimate_message_chars_for_object_error():
    manager = MessageHistoryManager()
    message = BrokenMessage()
    assert manager._estimate_message_chars(message) == len(str(message))


def test_get_message_role_exception():
    manager = MessageHistoryManager()
    message = BrokenMessage()
    assert manager._get_message_role(message) == ""


def test_message_history_manager_fallback_import(monkeypatch):
    monkeypatch.delitem(sys.modules, "pydantic_ai.messages", raising=False)
    original_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "pydantic_ai.messages":
            raise ImportError("missing")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    reloaded = importlib.reload(manager_module)
    assert reloaded.ModelMessage is dict

    monkeypatch.setattr(builtins, "__import__", original_import)
    importlib.reload(reloaded)
