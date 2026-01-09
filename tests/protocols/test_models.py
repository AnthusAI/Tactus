import pytest
from pydantic import ValidationError


def test_chat_message_human_interaction_type_accepts_new_name():
    from tactus.protocols.models import ChatMessage, HITLRequestType

    msg = ChatMessage(
        role="USER",
        content="hi",
        human_interaction_type="approval",
    )

    assert msg.human_interaction_type == HITLRequestType.APPROVAL
    assert msg.human_interaction == HITLRequestType.APPROVAL


def test_chat_message_human_interaction_type_accepts_legacy_aliases():
    from tactus.protocols.models import ChatMessage, HITLRequestType

    msg1 = ChatMessage(
        role="USER",
        content="hi",
        human_interaction="input",
    )
    assert msg1.human_interaction_type == HITLRequestType.INPUT

    msg2 = ChatMessage(
        role="USER",
        content="hi",
        humanInteraction="review",
    )
    assert msg2.human_interaction_type == HITLRequestType.REVIEW


def test_chat_message_human_interaction_type_rejects_unknown_values():
    from tactus.protocols.models import ChatMessage

    with pytest.raises(ValidationError):
        ChatMessage(
            role="USER",
            content="hi",
            human_interaction_type="made_up_type",
        )
