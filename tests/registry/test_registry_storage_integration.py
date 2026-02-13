import tempfile
from pathlib import Path

from tactus.registry.local import LocalRegistry
from tactus.registry.storage import LocalStorage


def test_local_registry_registers_artifact_with_storage():
    with tempfile.TemporaryDirectory() as tmpdir:
        storage = LocalStorage(base_dir=Path(tmpdir) / "artifacts")
        registry = LocalRegistry(registry_dir=tmpdir, storage=storage)

        version = registry.register(
            name="classifier",
            version="v1",
            backend_type="pytorch",
            backend_config={"path": "placeholder"},
            artifact=b"payload",
            artifact_filename="model.bin",
        )

        assert version.artifact_path is not None
        assert Path(version.artifact_path).exists()
        assert Path(version.artifact_path).read_bytes() == b"payload"
