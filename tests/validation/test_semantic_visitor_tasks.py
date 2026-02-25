import textwrap

from tactus.validation.validator import TactusValidator, ValidationMode


def _validate(source: str):
    return TactusValidator().validate(textwrap.dedent(source).strip(), ValidationMode.FULL)


def test_include_tasks_requires_task_only_source():
    result = _validate("""
        IncludeTasks("tasks.tac")
        alpha = Agent {
            provider = "openai",
            model = "gpt-4o-mini",
            system_prompt = "Test."
        }
        """)
    assert result.valid is False
    assert any(
        "IncludeTasks files must only contain Task declarations" in err.message
        for err in result.errors
    )


def test_include_tasks_requires_path_string():
    result = _validate("IncludeTasks()")
    assert result.valid is False
    assert any("IncludeTasks requires a path string" in err.message for err in result.errors)


def test_include_tasks_requires_literal_string():
    result = _validate("IncludeTasks(123)")
    assert result.valid is False
    assert any("IncludeTasks path must be a string literal" in err.message for err in result.errors)


def test_include_tasks_accepts_namespace_dict():
    result = _validate('IncludeTasks("tasks.tac", { namespace = "extras" })')
    assert result.valid is True
    assert result.registry.include_tasks[0]["namespace"] == "extras"


def test_assignment_based_retriever_heuristic_sets_id():
    result = _validate("""
        local TfVector = require("tactus.retrievers.tf_vector")
        miami_search = TfVector.Retriever { corpus = "docs" }
        """)
    assert result.valid is True
    assert result.registry.retrievers["miami_search"].config["retriever_id"] == "tf-vector"


def test_task_assignment_name_mismatch_records_error():
    result = _validate("""
        fetch = Task "run" { entry = function() end }
        """)
    assert result.valid is False
    assert any("Task name mismatch" in err.message for err in result.errors)


def test_task_requires_name():
    result = _validate("""
        Task { entry = function() end }
        """)
    assert result.valid is False
    assert any("Task name is required" in err.message for err in result.errors)


def test_assignment_based_retriever_heuristic_sets_id_from_alias():
    result = _validate("""
        local TfVectorRetriever = require("tactus.retrievers.tf_vector").Retriever
        miami_search = TfVectorRetriever { corpus = "docs" }
        """)
    assert result.valid is True
    assert result.registry.retrievers["miami_search"].config["retriever_id"] == "tf-vector"


def test_nested_task_name_mismatch_records_error():
    result = _validate("""
        Task "fetch" {
            NOAA = Task "Weather" { entry = function() end }
        }
        """)
    assert result.valid is False
    assert any("Task name mismatch" in err.message for err in result.errors)
