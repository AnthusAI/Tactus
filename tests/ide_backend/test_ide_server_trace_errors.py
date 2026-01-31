from tactus.ide import server as ide_server


def test_trace_run_requires_procedure(tmp_path):
    app = ide_server.create_app(initial_workspace=str(tmp_path))
    client = app.test_client()

    response = client.get("/api/traces/runs/run-1")
    assert response.status_code == 400
    assert "procedure parameter required" in response.get_json()["error"]


def test_trace_run_checkpoints_requires_procedure(tmp_path):
    app = ide_server.create_app(initial_workspace=str(tmp_path))
    client = app.test_client()

    response = client.get("/api/traces/runs/run-1/checkpoints")
    assert response.status_code == 400
    assert "procedure parameter required" in response.get_json()["error"]


def test_trace_run_checkpoint_requires_procedure(tmp_path):
    app = ide_server.create_app(initial_workspace=str(tmp_path))
    client = app.test_client()

    response = client.get("/api/traces/runs/run-1/checkpoints/1")
    assert response.status_code == 400
    assert "procedure parameter required" in response.get_json()["error"]


def test_trace_run_statistics_requires_procedure(tmp_path):
    app = ide_server.create_app(initial_workspace=str(tmp_path))
    client = app.test_client()

    response = client.get("/api/traces/runs/run-1/statistics")
    assert response.status_code == 400
    assert "procedure parameter required" in response.get_json()["error"]


def test_trace_run_events_missing_file(tmp_path):
    app = ide_server.create_app(initial_workspace=str(tmp_path))
    client = app.test_client()

    response = client.get("/api/traces/runs/run-1/events")
    assert response.status_code == 404
    assert "Events not found" in response.get_json()["error"]
