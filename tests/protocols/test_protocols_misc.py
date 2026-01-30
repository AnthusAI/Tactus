import asyncio
from datetime import datetime, timezone

from tactus.protocols.log_handler import LogHandler
from tactus.protocols.models import LogEvent, HITLRequest, HITLResponse
from tactus.protocols.control import (
    ControlChannel,
    ControlChannelConfig,
    ControlLoopConfig,
    ControlRequest,
    ControlRequestType,
)
from tactus.protocols.notification import (
    utc_now as notification_utc_now,
    ChannelCapabilities,
    NotificationDeliveryResult,
    PendingNotification,
    HITLResponsePayload,
    HITLResponseResult,
    NotificationChannel,
)
from tactus.protocols.result import TactusResult
from tactus.providers.base import Provider, ProviderConfig


def test_provider_config_model_string():
    config = ProviderConfig(provider_name="openai", model_id="gpt-4o")
    assert config.get_model_string() == "openai:gpt-4o"


def test_provider_protocol_stubs_return_ellipsis():
    assert Provider.validate_model("x") is None
    assert Provider.get_required_credentials() is None
    assert Provider.create_config("x") is None


def test_tactus_result_cost_returns_cost_stats():
    result = TactusResult(output="ok")
    assert result.cost() is result.cost_stats


def test_log_handler_protocol_stub_executes():
    event = LogEvent(level="INFO", message="hi")
    assert LogHandler.log(None, event) is None


def test_notification_models_roundtrip():
    now = datetime.now(timezone.utc)
    request = HITLRequest(request_type="input", message="Need input")
    delivery = NotificationDeliveryResult(
        channel_id="slack",
        external_message_id="msg-1",
        delivered_at=now,
        success=True,
    )
    pending = PendingNotification(
        request_id="req-1",
        procedure_id="proc",
        request=request,
        callback_url="http://callback",
    )
    payload = HITLResponsePayload(channel_id="slack", value="ok")
    response = HITLResponse(value="ok", responded_at=now, timed_out=False)
    result = HITLResponseResult(success=True, response=response)

    assert pending.deliveries == []
    assert delivery.channel_id == "slack"
    assert payload.value == "ok"
    assert result.response == response


def test_notification_utc_now_timezone_aware():
    now = notification_utc_now()
    assert now.tzinfo is not None


def test_notification_channel_protocol_stubs():
    assert NotificationChannel.channel_id.fget(None) is None
    assert NotificationChannel.capabilities.fget(None) is None


def test_notification_channel_async_stubs():
    request = HITLRequest(request_type="input", message="Need input")

    async def run():
        send_result = await NotificationChannel.send_notification(
            None,
            procedure_id="proc",
            request_id="req",
            request=request,
            callback_url="http://callback",
        )
        cancel_result = await NotificationChannel.cancel_notification(
            None, external_message_id="msg-1", reason="done"
        )
        return send_result, cancel_result

    send_result, cancel_result = asyncio.run(run())
    assert send_result is None
    assert cancel_result is None


def test_channel_capabilities_defaults():
    caps = ChannelCapabilities()
    assert caps.supports_approval is True
    assert caps.supports_interactive_buttons is False


def test_control_channel_protocol_stubs():
    assert ControlChannel.channel_id.fget(None) is None
    assert ControlChannel.capabilities.fget(None) is None


def test_control_channel_async_stubs():
    request = ControlRequest(
        request_id="req",
        procedure_id="proc",
        procedure_name="name",
        invocation_id="inv",
        started_at=datetime.now(timezone.utc),
        request_type=ControlRequestType.INPUT,
        message="Need input",
    )

    async def run():
        init_result = await ControlChannel.initialize(None)
        send_result = await ControlChannel.send(None, request)
        receive_result = await ControlChannel.receive(None)
        cancel_result = await ControlChannel.cancel(None, "msg", "done")
        shutdown_result = await ControlChannel.shutdown(None)
        return init_result, send_result, receive_result, cancel_result, shutdown_result

    init_result, send_result, receive_result, cancel_result, shutdown_result = asyncio.run(run())
    assert init_result is None
    assert send_result is None
    assert receive_result is None
    assert cancel_result is None
    assert shutdown_result is None


def test_control_config_defaults():
    channel_config = ControlChannelConfig()
    loop_config = ControlLoopConfig()
    assert channel_config.enabled is False
    assert loop_config.enabled is True
    assert loop_config.channels == {}
