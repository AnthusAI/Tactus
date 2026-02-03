import textwrap

from tactus.validation.validator import TactusValidator, ValidationMode


def _write(path, content: str) -> None:
    path.write_text(textwrap.dedent(content).strip() + "\n", encoding="utf-8")


def test_validate_file_includes_tasks(tmp_path):
    tasks_file = tmp_path / "tasks.tac"
    main_file = tmp_path / "main.tac"

    _write(
        tasks_file,
        """
        Task "fetch" { entry = function() end }
        """,
    )
    _write(
        main_file,
        """
        IncludeTasks("tasks.tac")
        """,
    )

    result = TactusValidator().validate_file(str(main_file), mode=ValidationMode.FULL)

    assert result.valid is True
    assert "fetch" in result.registry.tasks


def test_validate_file_includes_tasks_with_namespace(tmp_path):
    tasks_file = tmp_path / "tasks.tac"
    main_file = tmp_path / "main.tac"

    _write(
        tasks_file,
        """
        Task "fetch" { entry = function() end }
        """,
    )
    _write(
        main_file,
        """
        IncludeTasks("tasks.tac", "data")
        """,
    )

    result = TactusValidator().validate_file(str(main_file), mode=ValidationMode.FULL)

    assert result.valid is True
    assert "data" in result.registry.tasks
    assert "fetch" in result.registry.tasks["data"].children


def test_validate_file_includes_empty_task_file(tmp_path):
    tasks_file = tmp_path / "tasks.tac"
    main_file = tmp_path / "main.tac"

    _write(tasks_file, "")
    _write(main_file, 'IncludeTasks("tasks.tac")')

    result = TactusValidator().validate_file(str(main_file), mode=ValidationMode.FULL)

    assert result.valid is True


def test_validate_file_includes_tasks_missing_file(tmp_path):
    main_file = tmp_path / "main.tac"
    _write(main_file, 'IncludeTasks("missing.tac")')

    result = TactusValidator().validate_file(str(main_file), mode=ValidationMode.FULL)

    assert result.valid is False
    assert any("Included tasks file not found" in err.message for err in result.errors)


def test_validate_file_includes_tasks_cycle_detection(tmp_path):
    tasks_a = tmp_path / "tasks_a.tac"
    tasks_b = tmp_path / "tasks_b.tac"
    main_file = tmp_path / "main.tac"

    _write(tasks_a, 'IncludeTasks("tasks_b.tac")')
    _write(tasks_b, 'IncludeTasks("tasks_a.tac")')
    _write(main_file, 'IncludeTasks("tasks_a.tac")')

    result = TactusValidator().validate_file(str(main_file), mode=ValidationMode.FULL)

    assert result.valid is False
    assert any("IncludeTasks cycle detected" in err.message for err in result.errors)


def test_validate_file_skips_empty_include_path(tmp_path):
    main_file = tmp_path / "main.tac"
    _write(main_file, 'IncludeTasks("")')

    result = TactusValidator().validate_file(str(main_file), mode=ValidationMode.FULL)

    assert result.valid is True


def test_validate_file_rejects_non_task_declarations_in_include(tmp_path):
    tasks_file = tmp_path / "tasks.tac"
    main_file = tmp_path / "main.tac"

    _write(
        tasks_file,
        """
        Task "fetch" { entry = function() end }
        alpha = Agent {
            provider = "openai",
            model = "gpt-4o-mini",
            system_prompt = "Test."
        }
        """,
    )
    _write(
        main_file,
        """
        IncludeTasks("tasks.tac")
        """,
    )

    result = TactusValidator().validate_file(str(main_file), mode=ValidationMode.FULL)

    assert result.valid is False
    assert any(
        "IncludeTasks files must only contain Task declarations" in err.message
        for err in result.errors
    )


def test_validate_file_returns_include_validation_result(tmp_path):
    tasks_file = tmp_path / "tasks.tac"
    main_file = tmp_path / "main.tac"

    _write(tasks_file, 'Agent "alpha" { provider = "openai" }')
    _write(main_file, 'IncludeTasks("tasks.tac")')

    result = TactusValidator().validate_file(str(main_file), mode=ValidationMode.FULL)

    assert result.valid is False


def test_validate_file_rejects_duplicate_tasks(tmp_path):
    tasks_file = tmp_path / "tasks.tac"
    main_file = tmp_path / "main.tac"

    _write(
        tasks_file,
        """
        Task "fetch" { entry = function() end }
        """,
    )
    _write(
        main_file,
        """
        Task "fetch" { entry = function() end }
        IncludeTasks("tasks.tac")
        """,
    )

    result = TactusValidator().validate_file(str(main_file), mode=ValidationMode.FULL)

    assert result.valid is False
    assert any("Duplicate task 'fetch'" in err.message for err in result.errors)


def test_validate_file_rejects_duplicate_namespace(tmp_path):
    tasks_file = tmp_path / "tasks.tac"
    main_file = tmp_path / "main.tac"

    _write(tasks_file, 'Task "fetch" { entry = function() end }')
    _write(
        main_file,
        """
        Task "data" { entry = function() end }
        IncludeTasks("tasks.tac", "data")
        """,
    )

    result = TactusValidator().validate_file(str(main_file), mode=ValidationMode.FULL)

    assert result.valid is False
    assert any("Duplicate task namespace 'data'" in err.message for err in result.errors)


def test_include_has_non_task_declarations_none_returns_false():
    validator = TactusValidator()
    assert validator._include_has_non_task_declarations(None) is False
