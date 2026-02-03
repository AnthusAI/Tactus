from tactus.core.retriever_tasks import (
    RETRIEVER_TASKS,
    resolve_retriever_id,
    supported_retriever_tasks,
)


def test_resolve_retriever_id_handles_missing_config():
    assert resolve_retriever_id(None) is None
    assert resolve_retriever_id("not-a-dict") is None


def test_resolve_retriever_id_prefers_retriever_id():
    assert resolve_retriever_id({"retriever_id": "tf-vector"}) == "tf-vector"
    assert (
        resolve_retriever_id({"retriever_id": "  ", "retriever_type": "sqlite-full-text-search"})
        == "sqlite-full-text-search"
    )
    assert (
        resolve_retriever_id({"retriever_type": "embedding-index-file"}) == "embedding-index-file"
    )
    assert resolve_retriever_id({"retriever_id": " ", "retriever_type": "  "}) is None


def test_supported_retriever_tasks_returns_copy():
    tasks = supported_retriever_tasks("tf-vector")
    assert "index" in tasks
    tasks.add("extra")
    assert "extra" not in RETRIEVER_TASKS["tf-vector"]


def test_supported_retriever_tasks_unknown_returns_empty():
    assert supported_retriever_tasks(None) == set()
    assert supported_retriever_tasks("unknown") == set()
