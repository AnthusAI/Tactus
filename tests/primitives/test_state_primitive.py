from tactus.primitives.state import StatePrimitive


def test_state_set_and_get():
    state = StatePrimitive()
    state.set("key", "value")
    assert state.get("key") == "value"


def test_state_increment_and_append():
    state = StatePrimitive()
    state.set("counter", 1)
    state.increment("counter", 2)
    assert state.get("counter") == 3

    state.append("items", "a")
    state.append("items", "b")
    assert state.get("items") == ["a", "b"]


def test_state_defaults():
    state = StatePrimitive()
    assert state.get("missing", "default") == "default"
    assert "missing" not in state._state
