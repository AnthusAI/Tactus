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


def test_procedure_metadata_handles_non_dict_evaluations(monkeypatch, tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    proc_path = workspace / "proc.tac"
    proc_path.write_text("name('demo')")

    registry = SimpleNamespace(
        description=None,
        input_schema={},
        output_schema={},
        agents={},
        toolsets={},
        lua_tools={},
        gherkin_specifications=None,
        pydantic_evaluations=["not-a-dict"],
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
    assert payload["metadata"]["evaluations"]["runs"] == 1


def test_procedure_metadata_handles_partial_eval_dict(monkeypatch, tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    proc_path = workspace / "proc.tac"
    proc_path.write_text("name('demo')")

    registry = SimpleNamespace(
        description=None,
        input_schema={},
        output_schema={},
        agents={},
        toolsets={},
        lua_tools={},
        gherkin_specifications="Feature: Demo\nScenario: One\n",
        pydantic_evaluations={"dataset": "not-a-list", "evaluators": ["ok"], "runs": 3},
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
    assert payload["metadata"]["evaluations"]["dataset_count"] == 0
    assert payload["metadata"]["evaluations"]["evaluator_count"] == 1


def test_procedure_metadata_handles_empty_evaluations(monkeypatch, tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    proc_path = workspace / "proc.tac"
    proc_path.write_text("name('demo')")

    registry = SimpleNamespace(
        description=None,
        input_schema={},
        output_schema={},
        agents={},
        toolsets={},
        lua_tools={},
        gherkin_specifications=None,
        pydantic_evaluations={},
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
    assert payload["metadata"]["evaluations"] is None


def test_procedure_metadata_handles_non_list_evaluators(monkeypatch, tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    proc_path = workspace / "proc.tac"
    proc_path.write_text("name('demo')")

    registry = SimpleNamespace(
        description=None,
        input_schema={},
        output_schema={},
        agents={},
        toolsets={},
        lua_tools={},
        gherkin_specifications="Feature: Demo\nScenario: One\n",
        pydantic_evaluations={"dataset": [], "evaluators": "bad"},
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
    assert payload["metadata"]["evaluations"]["evaluator_count"] == 0


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
