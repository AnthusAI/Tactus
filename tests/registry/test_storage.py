import tempfile
from pathlib import Path

from tactus.registry.storage import LocalStorage, resolve_path


class TestLocalStorage:
    def test_save_load_exists_list(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = LocalStorage(base_dir=tmpdir)
            uri = storage.save(b"hello", "models/model.bin")
            assert Path(uri).exists()
            assert storage.exists(uri)
            assert storage.load(uri) == b"hello"

            listed = storage.list()
            assert any("model.bin" in p for p in listed)


def test_resolve_path_local_passthrough(tmp_path):
    local_file = tmp_path / "file.bin"
    local_file.write_bytes(b"abc")
    resolved = resolve_path(str(local_file))
    assert resolved == str(local_file)
