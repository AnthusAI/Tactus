import pytest

from tactus.core.dsl_stubs import create_dsl_stubs, lua_table_to_dict
from tactus.core.registry import RegistryBuilder


def test_lua_table_to_dict_none_returns_empty():
    assert lua_table_to_dict(None) == {}


def test_lua_table_to_dict_array_like():
    lua_table = {1: "a", 2: "b"}
    assert lua_table_to_dict(lua_table) == ["a", "b"]


def test_lua_table_to_dict_nested_dict():
    lua_table = {"a": 1, "b": {"c": 2}}
    assert lua_table_to_dict(lua_table) == {"a": 1, "b": {"c": 2}}


def test_filters_and_matchers_return_expected_tuples():
    builder = RegistryBuilder()
    stubs = create_dsl_stubs(builder)

    assert stubs["filters"]["last_n"](3) == ("last_n", 3)
    assert stubs["filters"]["first_n"](2) == ("first_n", 2)
    assert stubs["filters"]["token_budget"](100) == ("token_budget", 100)
    assert stubs["filters"]["head_tokens"](50) == ("head_tokens", 50)
    assert stubs["filters"]["tail_tokens"](25) == ("tail_tokens", 25)
    assert stubs["filters"]["by_role"]("user") == ("by_role", "user")
    assert stubs["filters"]["system_prefix"]() == ("system_prefix", None)
    assert stubs["filters"]["compose"](("last_n", 1), ("by_role", "user")) == (
        "compose",
        (("last_n", 1), ("by_role", "user")),
    )

    assert stubs["contains"]("hello") == ("contains", "hello")
    assert stubs["equals"](5) == ("equals", 5)
    assert stubs["matches"](r"^a") == ("matches", r"^a")


def test_tool_source_registration_and_validation():
    builder = RegistryBuilder()
    stubs = create_dsl_stubs(builder)

    with pytest.raises(TypeError, match="both 'use' and 'source'"):
        stubs["Tool"]({"use": "broker.host.ping", "source": "other"})

    with pytest.raises(TypeError, match="requires either a function"):
        stubs["Tool"]({"description": "no handler"})

    with pytest.raises(TypeError, match="Tool 'name' must be a string"):
        stubs["Tool"]({"name": 123, "use": "broker.host.ping"})

    with pytest.raises(TypeError, match="Tool 'name' cannot be empty"):
        stubs["Tool"]({"name": "   ", "use": "broker.host.ping"})

    handle = stubs["Tool"]({"name": "ping", "use": "broker.host.ping"})
    assert handle.name == "ping"
    assert "ping" in builder.registry.lua_tools
    assert builder.registry.lua_tools["ping"]["source"] == "broker.host.ping"


def test_agent_rejects_aliases_and_invalid_inline_tools():
    builder = RegistryBuilder()
    stubs = create_dsl_stubs(builder)

    with pytest.raises(ValueError, match="toolsets"):
        stubs["Agent"]({"toolsets": []})

    with pytest.raises(ValueError, match="inline_tools"):
        stubs["Agent"]({"inline_tools": "not-a-list"})

    with pytest.raises(ValueError, match="session"):
        stubs["Agent"]({"session": "legacy"})


def test_message_and_history_primitives():
    builder = RegistryBuilder()
    stubs = create_dsl_stubs(builder)

    with pytest.raises(ValueError, match="role"):
        stubs["Message"]({"content": "hi"})

    with pytest.raises(ValueError, match="content"):
        stubs["Message"]({"role": "user"})

    message = stubs["Message"]({"role": "user", "content": "hi", "meta": "ok"})
    assert message.to_dict() == {"role": "user", "content": "hi", "meta": "ok"}

    history = stubs["History"]()
    history.add(message)
    assert history.get()[-1]["content"] == "hi"
