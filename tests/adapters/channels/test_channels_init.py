import sys
import types

from tactus.adapters.channels import (
    load_channel,
    load_channels_from_config,
    load_default_channels,
)
from tactus.protocols.control import ControlLoopConfig


def test_load_channel_unknown():
    assert load_channel("missing", {}) is None


def test_load_channel_import_error(monkeypatch):
    monkeypatch.setattr(
        "tactus.adapters.channels._CHANNEL_LOADERS", {"bad": "missing.module:Thing"}
    )
    assert load_channel("bad", {}) is None


def test_load_channel_success(monkeypatch):
    module = types.ModuleType("fake_channel")

    class DummyChannel:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    module.DummyChannel = DummyChannel
    sys.modules["fake_channel"] = module

    monkeypatch.setattr(
        "tactus.adapters.channels._CHANNEL_LOADERS", {"ok": "fake_channel:DummyChannel"}
    )

    channel = load_channel("ok", {"x": 1})
    assert isinstance(channel, DummyChannel)
    assert channel.kwargs["x"] == 1


def test_load_channel_init_exception(monkeypatch):
    module = types.ModuleType("bad_channel")

    class ExplodingChannel:
        def __init__(self, **_kwargs):
            raise RuntimeError("boom")

    module.ExplodingChannel = ExplodingChannel
    sys.modules["bad_channel"] = module

    monkeypatch.setattr(
        "tactus.adapters.channels._CHANNEL_LOADERS", {"bad": "bad_channel:ExplodingChannel"}
    )

    assert load_channel("bad", {}) is None


def test_load_channels_from_config(monkeypatch):
    config = ControlLoopConfig(channels={"cli": {"enabled": "true"}})
    monkeypatch.setattr("tactus.adapters.channels.load_channel", lambda cid, cfg: cid)
    channels = load_channels_from_config(config)
    assert channels == ["cli"]


def test_load_channels_from_config_none(monkeypatch):
    monkeypatch.setattr("tactus.adapters.channels.load_default_channels", lambda: ["default"])
    assert load_channels_from_config() == ["default"]


def test_load_channels_from_config_auto_detection(monkeypatch):
    config = ControlLoopConfig(channels={"cli": {"enabled": "auto"}})
    monkeypatch.setattr("tactus.adapters.channels.sys.stdin.isatty", lambda: True)
    monkeypatch.setattr("tactus.adapters.channels.load_channel", lambda cid, cfg: cid)

    assert load_channels_from_config(config) == ["cli"]


def test_load_channels_from_config_disabled(monkeypatch):
    config = ControlLoopConfig(channels={"cli": {"enabled": "false"}})
    monkeypatch.setattr("tactus.adapters.channels.load_channel", lambda cid, cfg: cid)

    assert load_channels_from_config(config) == []


def test_load_channels_from_config_none_uses_isatty(monkeypatch):
    config = ControlLoopConfig(channels={"cli": {"enabled": None}})
    monkeypatch.setattr("tactus.adapters.channels.sys.stdin.isatty", lambda: False)
    monkeypatch.setattr("tactus.adapters.channels.load_channel", lambda cid, cfg: cid)

    assert load_channels_from_config(config) == []


def test_load_channels_from_config_string_true(monkeypatch):
    config = ControlLoopConfig(channels={"cli": {"enabled": "TrUe"}})
    monkeypatch.setattr("tactus.adapters.channels.load_channel", lambda cid, cfg: cid)
    assert load_channels_from_config(config) == ["cli"]


def test_load_channels_from_config_boolean_true(monkeypatch):
    config = ControlLoopConfig(channels={"cli": {"enabled": True}})
    monkeypatch.setattr("tactus.adapters.channels.load_channel", lambda cid, cfg: cid)
    assert load_channels_from_config(config) == ["cli"]


def test_load_channels_from_config_non_cli_channel(monkeypatch):
    config = ControlLoopConfig(channels={"ipc": {"enabled": True}})
    monkeypatch.setattr("tactus.adapters.channels.load_channel", lambda cid, cfg: cid)
    assert load_channels_from_config(config) == ["ipc"]


def test_load_channels_from_config_loader_returns_none(monkeypatch):
    config = ControlLoopConfig(channels={"cli": {"enabled": True}})
    monkeypatch.setattr("tactus.adapters.channels.load_channel", lambda cid, cfg: None)
    assert load_channels_from_config(config) == []


def test_load_channels_from_config_uses_defaults(monkeypatch):
    config = ControlLoopConfig(channels={})
    monkeypatch.setattr("tactus.adapters.channels.load_default_channels", lambda: ["default"])
    assert load_channels_from_config(config) == ["default"]


def test_load_default_channels(monkeypatch):
    monkeypatch.setattr("tactus.adapters.channels.sys.stdin.isatty", lambda: False)
    monkeypatch.setattr(
        "tactus.adapters.channels.ipc.IPCControlChannel",
        lambda procedure_id=None: types.SimpleNamespace(id="ipc"),
    )
    channels = load_default_channels()
    assert len(channels) == 1


def test_load_default_channels_with_cli(monkeypatch):
    monkeypatch.setattr("tactus.adapters.channels.sys.stdin.isatty", lambda: True)
    monkeypatch.setattr(
        "tactus.adapters.channels.ipc.IPCControlChannel",
        lambda procedure_id=None: types.SimpleNamespace(id="ipc"),
    )
    monkeypatch.setattr(
        "tactus.adapters.channels.cli.CLIControlChannel",
        lambda: types.SimpleNamespace(id="cli"),
    )

    channels = load_default_channels()
    assert len(channels) == 2
