from tactus.primitives.handles import ContextHandle, CorpusHandle, RetrieverHandle, CompactorHandle


def test_handle_repr_strings():
    assert repr(ContextHandle("ctx")) == "ContextHandle('ctx')"
    assert repr(CorpusHandle("corp")) == "CorpusHandle('corp')"
    assert repr(RetrieverHandle("ret")) == "RetrieverHandle('ret')"
    assert repr(CompactorHandle("comp")) == "CompactorHandle('comp')"
