from tactus.ide import server as ide_server


def test_hitl_response_routes_to_sse_channel(monkeypatch):
    recorded = {}

    class DummyChannel:
        def handle_ide_response(self, request_id, value):
            recorded["request_id"] = request_id
            recorded["value"] = value

    monkeypatch.setattr("tactus.adapters.channels.sse.SSEControlChannel", DummyChannel)
    app = ide_server.create_app()
    client = app.test_client()

    response = client.post("/api/hitl/response/req1", json={"value": "yes"})

    assert response.status_code == 200
    assert recorded["request_id"] == "req1"
    assert recorded["value"] == "yes"
