from datetime import timezone

from tactus.protocols.models import (
    HITLRequest,
    HITLResponse,
    ChatMessage,
    MessageClassification,
)
from tactus.protocols.notification import (
    ChannelCapabilities,
    NotificationDeliveryResult,
    PendingNotification,
    HITLResponsePayload,
    HITLResponseResult,
    NotificationChannelConfig,
    NotificationsConfig,
    utc_now,
    NotificationChannel,
)
from tactus.protocols.log_handler import LogHandler
from tactus.protocols.storage import StorageBackend


class DummyChannel:
    @property
    def channel_id(self):
        return "dummy"

    @property
    def capabilities(self):
        return ChannelCapabilities()

    async def send_notification(self, procedure_id, request_id, request, callback_url):
        return NotificationDeliveryResult(
            channel_id="dummy",
            external_message_id="123",
            delivered_at=utc_now(),
            success=True,
        )

    async def cancel_notification(self, external_message_id, reason="done"):
        return None


def test_utc_now_is_timezone_aware():
    now = utc_now()
    assert now.tzinfo is timezone.utc


def test_notification_models_defaults():
    request = HITLRequest(request_type="input", message="hello")
    pending = PendingNotification(
        request_id="req",
        procedure_id="proc",
        request=request,
        callback_url="http://example.com",
    )
    assert pending.responded is False
    assert pending.deliveries == []
    assert pending.created_at.tzinfo is timezone.utc

    delivery = NotificationDeliveryResult(
        channel_id="x",
        external_message_id="y",
        delivered_at=utc_now(),
        success=True,
    )
    assert delivery.error_message is None

    payload = HITLResponsePayload(channel_id="x", value="ok")
    assert payload.metadata == {}

    response = HITLResponse(value="yes", responded_at=utc_now())
    result = HITLResponseResult(success=True, response=response)
    assert result.already_responded is False


def test_notification_channel_protocol_runtime_checkable():
    assert isinstance(DummyChannel(), NotificationChannel)


def test_notifications_config_defaults():
    channel_config = NotificationChannelConfig()
    notifications_config = NotificationsConfig()
    assert channel_config.enabled is False
    assert notifications_config.enabled is False


def test_protocol_types_exposed():
    assert hasattr(LogHandler, "log")
    assert hasattr(StorageBackend, "load_procedure_metadata")


def test_chat_message_defaults_classification_from_role():
    message = ChatMessage(role="user", content="hello")

    assert message.classification == MessageClassification.CHAT
    assert message.human_interaction == MessageClassification.CHAT.value


def test_chat_message_maps_legacy_human_interaction():
    message = ChatMessage(role="user", content="hello", human_interaction="approval")

    assert message.classification == MessageClassification.PENDING_APPROVAL
    assert message.human_interaction == "approval"


def test_chat_message_respects_explicit_classification():
    message = ChatMessage(
        role="assistant",
        content="ok",
        classification="ALERT_ERROR",
    )

    assert message.classification == MessageClassification.ALERT_ERROR
    assert message.human_interaction == MessageClassification.ALERT_ERROR.value
