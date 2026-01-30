import pytest

from tactus.broker import server


def test_json_dumps_is_compact():
    assert server._json_dumps({"a": 1, "b": 2}) == '{"a":1,"b":2}'


def test_flatten_exceptions_handles_groups():
    group = ExceptionGroup(
        "root",
        [ValueError("one"), ExceptionGroup("nested", [RuntimeError("two")])],
    )
    leaves = server._flatten_exceptions(group)
    assert [type(exc) for exc in leaves] == [ValueError, RuntimeError]


def test_host_tool_registry_default_allows_ping_and_echo():
    registry = server.HostToolRegistry.default()
    assert registry.call("host.ping", {"x": 1}) == {"ok": True, "echo": {"x": 1}}
    assert registry.call("host.echo", {"y": 2}) == {"echo": {"y": 2}}


def test_host_tool_registry_rejects_unknown_tool():
    registry = server.HostToolRegistry.default()
    with pytest.raises(KeyError):
        registry.call("host.unknown", {})
