from tactus.testing.context import TactusTestContext


def test_run_procedure_invokes_async(tmp_path, monkeypatch):
    ctx = TactusTestContext(procedure_file=tmp_path / "proc.tac")
    called = {"value": False}

    async def fake_run():
        called["value"] = True

    monkeypatch.setattr(ctx, "run_procedure_async", fake_run)

    ctx.run_procedure()

    assert called["value"] is True
