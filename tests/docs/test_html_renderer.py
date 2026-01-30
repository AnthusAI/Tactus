from tactus.docs.html_renderer import HTMLRenderer
from tactus.docs.models import DocumentationTree, ModuleDoc


def test_html_renderer_renders_module_and_index():
    renderer = HTMLRenderer()
    module = ModuleDoc(
        name="demo",
        full_name="tactus.demo",
        file_path="demo.tac",
    )
    tree = DocumentationTree(root_path="/tmp/docs", modules=[module])

    module_html = renderer.render_module(module)
    index_html = renderer.render_index(tree)

    assert "demo" in module_html
    assert "demo" in index_html


def test_html_renderer_render_all_writes_files(tmp_path):
    renderer = HTMLRenderer()
    module = ModuleDoc(
        name="demo",
        full_name="tactus.demo",
        file_path="demo.tac",
    )
    tree = DocumentationTree(root_path=str(tmp_path), modules=[module])

    output_dir = tmp_path / "out"
    renderer.render_all(tree, output_dir)

    assert (output_dir / "index.html").exists()
    assert (output_dir / "demo.html").exists()


def test_html_renderer_accepts_custom_template_dir(tmp_path):
    templates_dir = tmp_path / "templates"
    templates_dir.mkdir()
    (templates_dir / "index.html").write_text("Index: {{ tree.modules|length }}")
    (templates_dir / "module.html").write_text("Module: {{ module.name }}")

    renderer = HTMLRenderer(template_dir=templates_dir)
    module = ModuleDoc(
        name="demo",
        full_name="tactus.demo",
        file_path="demo.tac",
    )
    tree = DocumentationTree(root_path=str(tmp_path), modules=[module])

    assert renderer.render_index(tree) == "Index: 1"
    assert renderer.render_module(module) == "Module: demo"


def test_html_renderer_markdown_filter():
    renderer = HTMLRenderer()
    rendered = renderer._markdown_filter("**bold**")
    assert "<strong>bold</strong>" in rendered
