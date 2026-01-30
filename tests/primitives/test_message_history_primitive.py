from tactus.core.message_history_manager import MessageHistoryManager
from tactus.primitives.message_history import MessageHistoryPrimitive


class FakeMessage:
    def __init__(self, role, content, msg_id=None, created_at=None):
        self.role = role
        self.content = content
        self.id = msg_id
        self.created_at = created_at


class FakeLuaTable:
    def __init__(self, items):
        self._items = items

    def items(self):
        return list(self._items)


def _seed_history(history: MessageHistoryPrimitive) -> str:
    history.clear()
    history.inject_system("System A")
    history.inject_system("System B")
    history.append({"role": "user", "content": "aaaa"})
    history.append({"role": "assistant", "content": "bbbb"})
    history.append({"role": "user", "content": "cccc"})
    checkpoint_id = history.checkpoint("mid")
    history.append({"role": "assistant", "content": "dddd"})
    history.append({"role": "user", "content": "eeee"})
    return checkpoint_id


def _count_messages(messages) -> int:
    return len(messages)


def test_append_and_get_assigns_metadata():
    manager = MessageHistoryManager()
    history = MessageHistoryPrimitive(message_history_manager=manager)

    history.append({"role": "user", "content": "hello"})
    messages = history.get()

    assert len(messages) == 1
    assert messages[0]["role"] == "user"
    assert messages[0]["content"] == "hello"
    assert "id" in messages[0]
    assert "created_at" in messages[0]


def test_append_no_manager_noop():
    history = MessageHistoryPrimitive(message_history_manager=None)
    history.append({"role": "user", "content": "hello"})
    assert history.get() == []


def test_reset_keeps_system_prefix():
    manager = MessageHistoryManager()
    history = MessageHistoryPrimitive(message_history_manager=manager)

    _seed_history(history)
    history.reset({"keep": "system_prefix"})

    messages = history.get()
    assert _count_messages(messages) == 2
    assert all(msg["role"] == "system" for msg in messages)


def test_reset_keep_system_all():
    manager = MessageHistoryManager()
    history = MessageHistoryPrimitive(message_history_manager=manager)

    _seed_history(history)
    history.append({"role": "system", "content": "later"})
    history.reset({"keep": "system_all"})

    messages = history.get()
    assert all(msg["role"] == "system" for msg in messages)
    assert _count_messages(messages) == 3


def test_reset_keep_none_clears():
    manager = MessageHistoryManager()
    history = MessageHistoryPrimitive(message_history_manager=manager)

    _seed_history(history)
    history.reset("none")

    assert history.get() == []


def test_head_and_tail_do_not_mutate():
    manager = MessageHistoryManager()
    history = MessageHistoryPrimitive(message_history_manager=manager)

    _seed_history(history)
    original_count = _count_messages(history.get())

    head = history.head(3)
    tail = history.tail(2)

    assert _count_messages(head) == 3
    assert _count_messages(tail) == 2
    assert _count_messages(history.get()) == original_count


def test_head_tail_zero_returns_empty():
    manager = MessageHistoryManager()
    history = MessageHistoryPrimitive(message_history_manager=manager)

    _seed_history(history)
    assert history.head(0) == []
    assert history.tail(0) == []


def test_head_tail_without_manager_empty():
    history = MessageHistoryPrimitive(message_history_manager=None)
    assert history.head(3) == []
    assert history.tail(2) == []


def test_slice_uses_one_based_indices():
    manager = MessageHistoryManager()
    history = MessageHistoryPrimitive(message_history_manager=manager)

    _seed_history(history)
    sliced = history.slice({"start": 2, "stop": 4})

    assert _count_messages(sliced) == 3
    assert sliced[0]["content"] == "System B"


def test_slice_without_manager_or_options():
    history = MessageHistoryPrimitive(message_history_manager=None)
    assert history.slice({"start": 1, "stop": 2}) == []

    history = MessageHistoryPrimitive(message_history_manager=MessageHistoryManager())
    assert history.slice(None) == []


def test_rewind_removes_last_messages():
    manager = MessageHistoryManager()
    history = MessageHistoryPrimitive(message_history_manager=manager)

    _seed_history(history)
    history.rewind(2)

    assert _count_messages(history.get()) == 5


def test_rewind_zero_no_change():
    manager = MessageHistoryManager()
    history = MessageHistoryPrimitive(message_history_manager=manager)

    _seed_history(history)
    history.rewind(0)

    assert _count_messages(history.get()) == 7


def test_rewind_to_checkpoint_id():
    manager = MessageHistoryManager()
    history = MessageHistoryPrimitive(message_history_manager=manager)

    checkpoint_id = _seed_history(history)
    history.rewind_to(checkpoint_id)

    assert _count_messages(history.get()) == 5


def test_rewind_to_invalid_id_no_change():
    manager = MessageHistoryManager()
    history = MessageHistoryPrimitive(message_history_manager=manager)

    _seed_history(history)
    history.rewind_to("not-a-number")

    assert _count_messages(history.get()) == 7


def test_rewind_to_missing_id_no_change():
    manager = MessageHistoryManager()
    history = MessageHistoryPrimitive(message_history_manager=manager)

    _seed_history(history)
    history.rewind_to(999999)

    assert _count_messages(history.get()) == 7


def test_rewind_no_manager_noop():
    history = MessageHistoryPrimitive(message_history_manager=None)
    history.rewind(2)
    history.rewind_to(1)


def test_tail_tokens_uses_budget():
    manager = MessageHistoryManager()
    history = MessageHistoryPrimitive(message_history_manager=manager)

    _seed_history(history)
    tail_tokens = history.tail_tokens(2)

    assert _count_messages(tail_tokens) == 2


def test_tail_tokens_without_manager():
    history = MessageHistoryPrimitive(message_history_manager=None)
    assert history.tail_tokens(2) == []


def test_keep_tail_tokens_mutates():
    manager = MessageHistoryManager()
    history = MessageHistoryPrimitive(message_history_manager=manager)

    _seed_history(history)
    history.keep_tail_tokens(2)

    assert _count_messages(history.get()) == 2


def test_keep_head_tail_without_manager():
    history = MessageHistoryPrimitive(message_history_manager=None)
    history.keep_head(1)
    history.keep_tail(1)
    history.keep_tail_tokens(1)


def test_keep_head_and_keep_tail_mutate():
    manager = MessageHistoryManager()
    history = MessageHistoryPrimitive(message_history_manager=manager)

    _seed_history(history)
    history.keep_head(4)
    assert _count_messages(history.get()) == 4

    _seed_history(history)
    history.keep_tail(3)
    assert _count_messages(history.get()) == 3


def test_checkpoint_records_name_and_returns_id():
    manager = MessageHistoryManager()
    history = MessageHistoryPrimitive(message_history_manager=manager)

    assert history.checkpoint("start") is None

    history.append({"role": "user", "content": "hello"})
    message_id = history.checkpoint("start")

    assert message_id == manager.get_checkpoint("start")


def test_checkpoint_with_non_string_name_does_not_record():
    manager = MessageHistoryManager()
    history = MessageHistoryPrimitive(message_history_manager=manager)

    history.append({"role": "user", "content": "hello"})
    message_id = history.checkpoint(123)

    assert message_id is not None
    assert manager.get_checkpoint("123") is None


def test_checkpoint_handles_object_message_id():
    manager = MessageHistoryManager()
    history = MessageHistoryPrimitive(message_history_manager=manager)
    manager.shared_history = [FakeMessage("user", "hi", msg_id=123)]

    assert history.checkpoint("start") == 123


def test_checkpoint_without_manager_returns_none():
    history = MessageHistoryPrimitive(message_history_manager=None)
    assert history.checkpoint("start") is None


def test_get_handles_object_messages():
    manager = MessageHistoryManager()
    history = MessageHistoryPrimitive(message_history_manager=manager)

    manager.histories["agent"] = [FakeMessage("user", "hi", msg_id=7, created_at="now")]
    history.agent_name = "agent"

    messages = history.get()
    assert messages[0]["role"] == "user"
    assert messages[0]["content"] == "hi"
    assert messages[0]["id"] == 7
    assert messages[0]["created_at"] == "now"


def test_get_handles_object_messages_without_metadata():
    manager = MessageHistoryManager()
    history = MessageHistoryPrimitive(message_history_manager=manager)

    manager.shared_history = [FakeMessage("user", "hi")]
    messages = history.get()

    assert messages[0]["role"] == "user"
    assert messages[0]["content"] == "hi"
    assert "id" not in messages[0]
    assert "created_at" not in messages[0]


def test_get_handles_bad_message_object():
    manager = MessageHistoryManager()
    history = MessageHistoryPrimitive(message_history_manager=manager)

    class BadMessage:
        def __getattr__(self, _name):
            raise RuntimeError("boom")

    manager.shared_history = [BadMessage()]
    messages = history.get()
    assert messages[0]["role"] == "unknown"


def test_normalize_messages_and_options():
    history = MessageHistoryPrimitive(message_history_manager=MessageHistoryManager())

    assert history._normalize_messages(({"role": "user", "content": "a"},)) == [
        {"role": "user", "content": "a"}
    ]
    lua_table = FakeLuaTable([(2, {"role": "user"}), (1, {"role": "system"})])
    assert history._normalize_messages(lua_table) == [
        {"role": "system"},
        {"role": "user"},
    ]
    assert history._normalize_message_data("hello")["content"] == "hello"
    assert history._normalize_message_data(None) == {}
    assert history._normalize_options(None) == {}


def test_normalize_messages_none_and_iterable():
    history = MessageHistoryPrimitive(message_history_manager=MessageHistoryManager())
    assert history._normalize_messages(None) == []
    assert history._normalize_messages(iter([{"role": "user"}])) == [{"role": "user"}]


def test_normalize_options_items_failure_returns_empty():
    history = MessageHistoryPrimitive(message_history_manager=MessageHistoryManager())

    class BadOptions:
        def items(self):
            raise ValueError("boom")

    assert history._normalize_options(BadOptions()) == {}


def test_normalize_messages_tuple_and_non_int_keys():
    history = MessageHistoryPrimitive(message_history_manager=MessageHistoryManager())

    assert history._normalize_messages(({"role": "user"},)) == [{"role": "user"}]

    lua_table = FakeLuaTable([("b", {"role": "user"}), ("a", {"role": "system"})])
    assert history._normalize_messages(lua_table) == [
        {"role": "user"},
        {"role": "system"},
    ]


def test_normalize_message_data_items_failure_falls_back():
    history = MessageHistoryPrimitive(message_history_manager=MessageHistoryManager())

    class BrokenItems:
        def items(self):
            raise ValueError("boom")

    result = history._normalize_message_data(BrokenItems())
    assert result["role"] == "user"
    assert result["content"].startswith("<")


def test_serialize_messages_fallback_on_bad_message():
    manager = MessageHistoryManager()
    history = MessageHistoryPrimitive(message_history_manager=manager)

    class BadMessage:
        def __getattr__(self, _name):
            raise RuntimeError("boom")

    result = history._serialize_messages([BadMessage()])
    assert result[0]["role"] == "unknown"


def test_serialize_messages_object_with_id_and_created_at():
    manager = MessageHistoryManager()
    history = MessageHistoryPrimitive(message_history_manager=manager)

    result = history._serialize_messages([FakeMessage("user", "hi", msg_id=9, created_at="now")])
    assert result[0]["id"] == 9
    assert result[0]["created_at"] == "now"


def test_serialize_messages_object_without_metadata():
    manager = MessageHistoryManager()
    history = MessageHistoryPrimitive(message_history_manager=manager)

    result = history._serialize_messages([FakeMessage("user", "hi")])
    assert result[0]["role"] == "user"
    assert result[0]["content"] == "hi"
    assert "id" not in result[0]
    assert "created_at" not in result[0]


def test_get_history_ref_without_manager():
    history = MessageHistoryPrimitive(message_history_manager=None)
    assert history._get_history_ref() == []


def test_load_and_save_to_node_noops():
    history = MessageHistoryPrimitive(message_history_manager=MessageHistoryManager())
    history.load_from_node(object())
    history.save_to_node(object())


def test_clear_with_and_without_agent_name():
    manager = MessageHistoryManager()
    history = MessageHistoryPrimitive(message_history_manager=manager, agent_name="agent")
    history.append({"role": "user", "content": "hi"})
    history.clear()
    assert manager.histories.get("agent") == []

    history = MessageHistoryPrimitive(message_history_manager=manager)
    history.append({"role": "user", "content": "hi"})
    history.clear()
    assert manager.shared_history == []


def test_clear_without_manager_noop():
    history = MessageHistoryPrimitive(message_history_manager=None)
    history.clear()


def test_replace_without_manager_noop():
    history = MessageHistoryPrimitive(message_history_manager=None)
    history.replace([{"role": "user", "content": "hi"}])


def test_replace_with_agent_name_updates_agent_history():
    manager = MessageHistoryManager()
    history = MessageHistoryPrimitive(message_history_manager=manager, agent_name="agent")

    history.replace([{"role": "user", "content": "hi"}])
    assert manager.histories["agent"][0]["role"] == "user"


def test_reset_with_string_keep():
    manager = MessageHistoryManager()
    history = MessageHistoryPrimitive(message_history_manager=manager)
    _seed_history(history)

    history.reset("system_all")
    assert all(msg["role"] == "system" for msg in history.get())


def test_reset_without_manager_noop():
    history = MessageHistoryPrimitive(message_history_manager=None)
    history.reset({"keep": "none"})


def test_reset_with_non_string_options_keeps_default():
    manager = MessageHistoryManager()
    history = MessageHistoryPrimitive(message_history_manager=manager)
    _seed_history(history)

    history.reset(123)
    messages = history.get()
    assert _count_messages(messages) == 2
    assert all(msg["role"] == "system" for msg in messages)


def test_fallback_types_when_pydantic_ai_missing():
    import importlib
    import sys
    import types

    import tactus.primitives.message_history as message_history

    original_pydantic = sys.modules.get("pydantic_ai")
    original_messages = sys.modules.get("pydantic_ai.messages")
    sys.modules["pydantic_ai"] = types.ModuleType("pydantic_ai")
    sys.modules.pop("pydantic_ai.messages", None)

    try:
        reloaded = importlib.reload(message_history)
        assert reloaded.ModelMessage is dict
        assert reloaded.ModelRequest is dict
        assert reloaded.ModelResponse is dict
        assert reloaded.TextPart is dict
    finally:
        if original_pydantic is None:
            sys.modules.pop("pydantic_ai", None)
        else:
            sys.modules["pydantic_ai"] = original_pydantic
        if original_messages is not None:
            sys.modules["pydantic_ai.messages"] = original_messages
        else:
            sys.modules.pop("pydantic_ai.messages", None)
        importlib.reload(message_history)
