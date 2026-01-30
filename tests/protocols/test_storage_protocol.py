from tactus.protocols.storage import StorageBackend


def test_storage_backend_protocol_surface():
    required = {
        "load_procedure_metadata",
        "save_procedure_metadata",
        "update_procedure_status",
        "get_state",
        "set_state",
    }
    assert required.issubset(set(dir(StorageBackend)))
