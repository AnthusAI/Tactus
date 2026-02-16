"""Tests for documentation models."""

from tactus.docs.models import DocumentationTree, ModuleDoc


def test_documentation_tree_getters():
    module = ModuleDoc(
        name="classify",
        full_name="tactus.text.classify",
        file_path="/tmp/classify.spec.tac",
    )
    tree = DocumentationTree(root_path="/tmp", modules=[module])

    assert tree.get_module("classify") is module
    assert tree.get_module("tactus.text.classify") is module
    assert tree.get_module("missing") is None

    prefixed = tree.get_modules_by_prefix("tactus.text")
    assert prefixed == [module]
