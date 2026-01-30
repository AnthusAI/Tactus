import builtins
import importlib.util

import pytest

import tactus.stdlib.classify.fuzzy as fuzzy


def test_fuzzy_import_error_falls_back():
    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "rapidfuzz":
            raise ImportError("missing")
        return real_import(name, *args, **kwargs)

    spec = importlib.util.spec_from_file_location(
        "tactus.stdlib.classify.fuzzy_missing", fuzzy.__file__
    )
    module = importlib.util.module_from_spec(spec)
    try:
        builtins.__import__ = fake_import
        spec.loader.exec_module(module)
    finally:
        builtins.__import__ = real_import

    assert module.HAS_RAPIDFUZZ is False
    with pytest.raises(ValueError, match="requires rapidfuzz"):
        module.calculate_similarity("a", "b", algorithm="token_sort_ratio")
