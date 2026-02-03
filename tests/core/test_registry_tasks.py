from tactus.core.registry import RegistryBuilder


def test_register_retriever_maps_query_pipeline_fields():
    builder = RegistryBuilder()
    builder.register_retriever(
        "search",
        {
            "corpus": "docs",
            "retriever_type": "tf-vector",
            "configuration": {
                "pipeline": {
                    "query": {
                        "limit": 3,
                        "include_metadata": True,
                    }
                }
            },
        },
    )
    retriever = builder.registry.retrievers["search"]
    assert retriever.config["retriever_id"] == "tf-vector"
    assert retriever.config["limit"] == 3
    assert retriever.config["include_metadata"] is True


def test_register_retriever_skips_non_dict_query_pipeline():
    builder = RegistryBuilder()
    builder.register_retriever(
        "search",
        {
            "corpus": "docs",
            "retriever_type": "tf-vector",
            "configuration": {"pipeline": {"query": "not-a-dict"}},
        },
    )
    retriever = builder.registry.retrievers["search"]
    assert "limit" not in retriever.config


def test_register_task_records_errors_for_invalid_names():
    builder = RegistryBuilder()
    builder.register_task("", {})
    builder.register_task("bad:name", {})
    assert any("Task name is required" in msg.message for msg in builder.validation_messages)
    assert any("may not contain ':'" in msg.message for msg in builder.validation_messages)


def test_register_task_validation_error_records():
    builder = RegistryBuilder()
    builder.register_task("broken", {"children": "not-a-dict"})
    assert any("Invalid task" in msg.message for msg in builder.validation_messages)


def test_register_task_duplicate_and_parent_errors():
    builder = RegistryBuilder()
    builder.register_task("fetch", {})
    builder.register_task("fetch", {})
    builder.register_task("child", {}, parent="missing")
    builder.register_task("parent", {})
    builder.register_task("child", {}, parent="parent")
    builder.register_task("child", {}, parent="parent")

    messages = [msg.message for msg in builder.validation_messages]
    assert any("Duplicate task 'fetch'" in message for message in messages)
    assert any("Parent task 'missing' not found" in message for message in messages)
    assert any("Duplicate task 'parent:child'" in message for message in messages)
