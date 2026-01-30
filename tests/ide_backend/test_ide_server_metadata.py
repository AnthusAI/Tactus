from types import SimpleNamespace

from tactus.ide import server as ide_server


def test_procedure_metadata_requires_path():
    app = ide_server.create_app()
    client = app.test_client()

    response = client.get("/api/procedure/metadata")

    assert response.status_code == 400


def test_procedure_metadata_returns_registry(monkeypatch, tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    proc_path = workspace / "proc.tac"
    proc_path.write_text("name('demo')")

    agent = SimpleNamespace(
        name="agent",
        provider="openai",
        model="gpt-4o",
        system_prompt="hi",
        tools=["toolA"],
    )
    registry = SimpleNamespace(
        description="demo",
        input_schema={"param": {"type": "string"}},
        output_schema={"out": {"type": "string"}},
        agents={"agent": agent},
        toolsets={"set": {"tools": ["toolB"]}},
        lua_tools={"lua_tool": {}},
        gherkin_specifications="Feature: Demo\nScenario: One\n",
        pydantic_evaluations={"dataset": [{"input": "x"}], "evaluators": [{"name": "e"}]},
    )
    result = SimpleNamespace(registry=registry, errors=[])

    class DummyValidator:
        def validate_file(self, _path, _mode):
            return result

    monkeypatch.setattr(ide_server, "TactusValidator", DummyValidator)
    monkeypatch.setattr(ide_server, "WORKSPACE_ROOT", str(workspace))

    app = ide_server.create_app()
    client = app.test_client()

    response = client.get("/api/procedure/metadata", query_string={"path": "proc.tac"})
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["success"] is True
    assert payload["metadata"]["description"] == "demo"
    assert "toolA" in payload["metadata"]["tools"]
    assert payload["metadata"]["specifications"]["scenario_count"] == 1
    assert payload["metadata"]["evaluations"]["dataset_count"] == 1


def test_procedure_metadata_handles_missing_registry(monkeypatch, tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    proc_path = workspace / "proc.tac"
    proc_path.write_text("name('demo')")

    result = SimpleNamespace(registry=None, errors=[SimpleNamespace(message="bad", location=None)])

    class DummyValidator:
        def validate_file(self, _path, _mode):
            return result

    monkeypatch.setattr(ide_server, "TactusValidator", DummyValidator)
    monkeypatch.setattr(ide_server, "WORKSPACE_ROOT", str(workspace))

    app = ide_server.create_app()
    client = app.test_client()

    response = client.get("/api/procedure/metadata", query_string={"path": "proc.tac"})

    assert response.status_code == 400
