from tactus.adapters.memory import MemoryStorage


def test_load_creates_metadata_once():
    storage = MemoryStorage()
    first = storage.load_procedure_metadata("proc")
    second = storage.load_procedure_metadata("proc")
    assert first is second


def test_save_overwrites_metadata():
    storage = MemoryStorage()
    metadata = storage.load_procedure_metadata("proc")
    metadata.status = "DONE"
    storage.save_procedure_metadata("proc", metadata)
    assert storage.load_procedure_metadata("proc").status == "DONE"


def test_update_procedure_status_sets_waiting_message():
    storage = MemoryStorage()
    storage.update_procedure_status("proc", "WAITING", waiting_on_message_id="msg")
    metadata = storage.load_procedure_metadata("proc")
    assert metadata.status == "WAITING"
    assert metadata.waiting_on_message_id == "msg"


def test_get_and_set_state():
    storage = MemoryStorage()
    assert storage.get_state("proc") == {}
    storage.set_state("proc", {"x": 1})
    assert storage.get_state("proc") == {"x": 1}
