from pathlib import Path

from tactus.testing.behave_integration import (
    BehaveFeatureGenerator,
    BehaveStepsGenerator,
    BehaveEnvironmentGenerator,
    setup_behave_directory,
    load_custom_steps_from_lua,
)
from tactus.testing.models import ParsedFeature, ParsedScenario, ParsedStep
from tactus.testing.steps.registry import StepRegistry
from tactus.testing.steps.custom import CustomStepManager


def test_feature_generator_writes_tags_and_steps(tmp_path):
    feature = ParsedFeature(
        name="Demo Feature",
        description="Line one\nLine two",
        tags=["fast"],
        scenarios=[
            ParsedScenario(
                name="Scenario A",
                tags=["smoke"],
                steps=[ParsedStep(keyword="Given", message="something")],
            )
        ],
    )

    gen = BehaveFeatureGenerator()
    path = gen.generate(feature, tmp_path)

    content = path.read_text()
    assert "@fast" in content
    assert "Feature: Demo Feature" in content
    assert "Scenario: Scenario A" in content
    assert "Given something" in content
    assert "@scenario_scenario_a" in content


def test_steps_generator_writes_wrapper(tmp_path):
    registry = StepRegistry()
    registry.register(
        r"the output (?P<key>\\w+) should be (?P<value>.+)", lambda *args, **kwargs: None
    )
    custom = CustomStepManager()

    gen = BehaveStepsGenerator()
    steps_path = gen.generate(registry, custom, tmp_path)

    content = steps_path.read_text()
    assert "use_step_matcher('parse')" in content
    assert "builtin." in content
    assert "def step_" in content


def test_steps_generator_regex_helpers():
    gen = BehaveStepsGenerator()

    parse_pattern = gen._regex_to_parse_pattern(r"the output (?P<key>\\w+) should be (?P<value>.+)")
    assert "{key}" in parse_pattern
    assert "{value}" in parse_pattern

    func_name = gen._pattern_to_func_name("the output (?P<key>\\w+)")
    assert func_name.startswith("step_")


def test_environment_generator_writes_file(tmp_path):
    env = BehaveEnvironmentGenerator()
    env_path = env.generate(
        tmp_path,
        Path("procedure.tac"),
        mock_tools={"tool": "ok"},
        params={"x": 1},
        mcp_servers={"local": {"command": "true"}},
        tool_paths=["tools"],
        mocked=True,
    )

    content = env_path.read_text()
    assert "before_all" in content
    assert "before_scenario" in content
    assert "after_scenario" in content


def test_steps_generator_includes_custom_steps(tmp_path):
    registry = StepRegistry()
    registry.register(r"a step", lambda *args, **kwargs: None)
    custom = CustomStepManager()
    custom.register_from_lua(r"custom (.+)", lambda *args, **kwargs: None)

    gen = BehaveStepsGenerator()
    steps_path = gen.generate(registry, custom, tmp_path)

    content = steps_path.read_text()
    assert "use_step_matcher('re')" in content
    assert "custom_step_0" in content


def test_load_custom_steps_from_lua_handles_errors(tmp_path):
    bad_file = tmp_path / "bad.tac"
    bad_file.write_text("this is not lua")

    result = load_custom_steps_from_lua(bad_file)

    assert result == {}


def test_setup_behave_directory_creates_structure(tmp_path):
    feature = ParsedFeature(
        name="Demo",
        scenarios=[ParsedScenario(name="S", steps=[ParsedStep(keyword="Given", message="x")])],
    )
    registry = StepRegistry()
    registry.register(r"a step", lambda *args, **kwargs: None)
    custom = CustomStepManager()

    work_dir = setup_behave_directory(
        parsed_feature=feature,
        step_registry=registry,
        custom_steps=custom,
        procedure_file=tmp_path / "proc.tac",
        work_dir=tmp_path / "behave",
    )

    assert (work_dir / "environment.py").exists()
    assert list(work_dir.glob("*.feature"))
    assert (work_dir / "steps").exists()
