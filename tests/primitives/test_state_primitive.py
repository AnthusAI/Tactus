from tactus.primitives.state import StatePrimitive


def test_state_defaults_and_get_set():
    state = StatePrimitive({"count": {"default": 1}})
    assert state.get("count") == 1
    state.set("count", 2)
    assert state.get("count") == 2


def test_state_increment_and_append():
    state = StatePrimitive()
    assert state.increment("hits") == 1
    assert state.increment("hits", 2) == 3

    state.set("items", "a")
    state.append("items", "b")
    assert state.get("items") == ["a", "b"]


def test_state_increment_resets_non_numeric():
    state = StatePrimitive()
    state.set("hits", "oops")

    assert state.increment("hits") == 1


def test_state_all_clear_and_validation():
    state = StatePrimitive({"name": {"type": "string"}})
    state.set("name", 123)
    assert state.all()["name"] == 123
    state.clear()
    assert state.all() == {}
    assert state._is_value_matching_schema_type(1, "unknown") is True


def test_state_set_with_matching_schema_type():
    state = StatePrimitive({"name": {"type": "string"}})
    state.set("name", "ok")

    assert state.get("name") == "ok"


def test_state_repr_includes_key_count():
    state = StatePrimitive()
    state.set("a", 1)

    assert "1 keys" in repr(state)
