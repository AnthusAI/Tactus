"""Tests for docs package entrypoints."""

import tactus.docs as docs


def test_generate_docs_runs_with_custom_renderer(tmp_path, monkeypatch):
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir()
    (input_dir / "module.spec.tac").write_text("--[[doc\nDocs\n]]", encoding="utf-8")

    called = {}

    class FakeRenderer:
        def render_all(self, tree, output_dir):
            called["modules"] = len(tree.modules)
            output_dir.mkdir(parents=True, exist_ok=True)
            (output_dir / "index.html").write_text("ok", encoding="utf-8")

    monkeypatch.setattr(docs, "HTMLRenderer", lambda: FakeRenderer())

    docs.generate_docs(input_dir, output_dir)

    assert called["modules"] == 1
    assert (output_dir / "index.html").exists()
