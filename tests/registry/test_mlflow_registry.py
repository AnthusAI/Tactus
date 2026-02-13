from types import SimpleNamespace

from tactus.registry.mlflow import MLflowRegistry


class FakeClient:
    def __init__(self):
        self.versions = []

    def create_model_version(self, name, source, run_id=None):
        version = len(self.versions) + 1
        mv = SimpleNamespace(version=version, source=source, tags={}, creation_timestamp=0)
        self.versions.append(mv)
        return mv

    def set_model_version_tag(self, name, version, **kwargs):
        pass

    def delete_model_version_tag(self, name, version, tag_key):
        pass

    def search_model_versions(self, filter_string):
        return self.versions

    def get_model_version(self, name, version):
        for mv in self.versions:
            if str(mv.version) == str(version):
                return mv
        raise KeyError(version)


def test_mlflow_registry_register_and_list():
    client = FakeClient()
    registry = MLflowRegistry(client=client)

    mv = registry.register(
        name="demo",
        version="1",
        backend_type="pytorch",
        backend_config={"path": "/tmp/model.pt"},
        tags=["champion"],
    )

    assert mv.version_id == "1"
    versions = registry.list_versions("demo")
    assert len(versions) == 1
    assert versions[0].artifact_path == "/tmp/model.pt"
