import pytest

from tactus.protocols.chat_recorder import ChatRecorder
from tactus.protocols.hitl import HITLHandler
from tactus.protocols.storage import StorageBackend


def test_storage_protocol_methods_execute():
    assert StorageBackend.load_procedure_metadata(None, "proc") is None
    assert StorageBackend.save_procedure_metadata(None, "proc", None) is None
    assert StorageBackend.update_procedure_status(None, "proc", "RUNNING") is None
    assert StorageBackend.get_state(None, "proc") is None
    assert StorageBackend.set_state(None, "proc", {}) is None


@pytest.mark.asyncio
async def test_chat_recorder_protocol_methods_execute():
    assert await ChatRecorder.start_session(None, "proc") is None
    assert await ChatRecorder.record_message(None, None) is None
    assert await ChatRecorder.end_session(None, "session") is None
    assert await ChatRecorder.get_session_messages(None, "session") is None


def test_hitl_handler_protocol_methods_execute():
    assert HITLHandler.request_interaction(None, "proc", None) is None
    assert HITLHandler.check_pending_response(None, "proc", "msg") is None
    assert HITLHandler.cancel_pending_request(None, "proc", "msg") is None
