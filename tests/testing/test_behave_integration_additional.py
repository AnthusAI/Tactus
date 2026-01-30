from pathlib import Path

from tactus.testing import behave_integration
from tactus.testing.models import ParsedFeature, ParsedScenario, ParsedStep
from tactus.testing.steps.custom import CustomStepManager
from tactus.testing.steps.registry import StepRegistry


def test_load_custom_steps_from_lua_returns_empty_on_error(monkeypatch, tmp_path: Path):
    class FakeSandbox:
        def set_global(self, _name, _value):
            return None

        def execute(self, _source):
            raise RuntimeError("boom")

    monkeypatch.setattr("tactus.core.lua_sandbox.LuaSandbox", FakeSandbox)

    proc = tmp_path / "proc.tac"
    proc.write_text("Step('x', function() end)")

    result = behave_integration.load_custom_steps_from_lua(proc)

    assert result == {}


def test_load_custom_steps_in_context_returns_empty_on_error(monkeypatch, tmp_path: Path):
    class FakeSandbox:
        def set_global(self, _name, _value):
            return None

        def execute(self, _source):
            raise RuntimeError("boom")

    class DummyRuntime:
        tool_primitive = None
        execution_context = None
        registry = None
        log_handler = None
        mock_manager = None

    class DummyContext:
        def __init__(self, procedure_file):
            self.procedure_file = procedure_file
            self.runtime = None

        def setup_runtime(self):
            self.runtime = DummyRuntime()

    monkeypatch.setattr("tactus.core.lua_sandbox.LuaSandbox", FakeSandbox)

    proc = tmp_path / "proc.tac"
    proc.write_text("Step('x', function() end)")

    ctx = DummyContext(proc)
    result = behave_integration.load_custom_steps_in_context(ctx)

    assert result == {}


def test_load_custom_steps_from_lua_returns_custom_steps(monkeypatch, tmp_path: Path):
    class FakeSandbox:
        def set_global(self, _name, _value):
            return None

        def execute(self, _source):
            return None

    class FakeRegistry:
        custom_steps = {"Given x": object()}

    class FakeResult:
        registry = FakeRegistry()

    class FakeBuilder:
        def validate(self):
            return FakeResult()

    def fake_create_dsl_stubs(_builder, _tool_primitive=None, _mock_manager=None, **_kwargs):
        return {"_registries": object(), "_tactus_register_binding": object()}

    monkeypatch.setattr("tactus.core.lua_sandbox.LuaSandbox", FakeSandbox)
    monkeypatch.setattr("tactus.core.registry.RegistryBuilder", FakeBuilder)
    monkeypatch.setattr("tactus.core.dsl_stubs.create_dsl_stubs", fake_create_dsl_stubs)

    proc = tmp_path / "proc.tac"
    proc.write_text("Step('Given x', function() end)")

    result = behave_integration.load_custom_steps_from_lua(proc)

    assert result == {"Given x": FakeRegistry.custom_steps["Given x"]}


def test_load_custom_steps_in_context_returns_custom_steps(monkeypatch, tmp_path: Path):
    class FakeSandbox:
        def set_global(self, _name, _value):
            return None

        def execute(self, _source):
            return None

    class FakeRegistry:
        custom_steps = {"Given y": object()}

    class FakeResult:
        registry = FakeRegistry()

    class FakeBuilder:
        def validate(self):
            return FakeResult()

    class DummyRuntime:
        tool_primitive = None
        execution_context = None
        registry = None
        log_handler = None

    class DummyContext:
        def __init__(self, procedure_file):
            self.procedure_file = procedure_file
            self.runtime = DummyRuntime()

        def setup_runtime(self):
            return None

    def fake_create_dsl_stubs(_builder, _tool_primitive=None, _mock_manager=None, **_kwargs):
        return {"_registries": object(), "_tactus_register_binding": object()}

    class FakeMockManager:
        pass

    monkeypatch.setattr("tactus.core.lua_sandbox.LuaSandbox", FakeSandbox)
    monkeypatch.setattr("tactus.core.registry.RegistryBuilder", FakeBuilder)
    monkeypatch.setattr("tactus.core.dsl_stubs.create_dsl_stubs", fake_create_dsl_stubs)
    monkeypatch.setattr("tactus.core.mocking.MockManager", FakeMockManager)

    proc = tmp_path / "proc.tac"
    proc.write_text("Step('Given y', function() end)")

    ctx = DummyContext(proc)
    result = behave_integration.load_custom_steps_in_context(ctx)

    assert result == {"Given y": FakeRegistry.custom_steps["Given y"]}


def test_load_custom_steps_from_lua_returns_empty_when_no_steps(monkeypatch, tmp_path: Path):
    class FakeSandbox:
        def set_global(self, _name, _value):
            return None

        def execute(self, _source):
            return None

    class FakeRegistry:
        custom_steps = {}

    class FakeResult:
        registry = FakeRegistry()

    class FakeBuilder:
        def validate(self):
            return FakeResult()

    def fake_create_dsl_stubs(_builder, _tool_primitive=None, _mock_manager=None, **_kwargs):
        return {}

    monkeypatch.setattr("tactus.core.lua_sandbox.LuaSandbox", FakeSandbox)
    monkeypatch.setattr("tactus.core.registry.RegistryBuilder", FakeBuilder)
    monkeypatch.setattr("tactus.core.dsl_stubs.create_dsl_stubs", fake_create_dsl_stubs)

    proc = tmp_path / "proc.tac"
    proc.write_text("Step('Given z', function() end)")

    result = behave_integration.load_custom_steps_from_lua(proc)

    assert result == {}


def test_load_custom_steps_in_context_returns_empty_when_no_steps(monkeypatch, tmp_path: Path):
    class FakeSandbox:
        def set_global(self, _name, _value):
            return None

        def execute(self, _source):
            return None

    class FakeRegistry:
        custom_steps = {}

    class FakeResult:
        registry = FakeRegistry()

    class FakeBuilder:
        def validate(self):
            return FakeResult()

    class DummyRuntime:
        tool_primitive = None
        execution_context = None
        registry = None
        log_handler = None
        mock_manager = object()

    class DummyContext:
        def __init__(self, procedure_file):
            self.procedure_file = procedure_file
            self.runtime = DummyRuntime()

        def setup_runtime(self):
            return None

    def fake_create_dsl_stubs(_builder, _tool_primitive=None, _mock_manager=None, **_kwargs):
        return {}

    monkeypatch.setattr("tactus.core.lua_sandbox.LuaSandbox", FakeSandbox)
    monkeypatch.setattr("tactus.core.registry.RegistryBuilder", FakeBuilder)
    monkeypatch.setattr("tactus.core.dsl_stubs.create_dsl_stubs", fake_create_dsl_stubs)

    proc = tmp_path / "proc.tac"
    proc.write_text("Step('Given z', function() end)")

    ctx = DummyContext(proc)
    result = behave_integration.load_custom_steps_in_context(ctx)

    assert result == {}


def test_steps_generator_deduplicates_patterns(tmp_path: Path):
    class FakePattern:
        def __init__(self, pattern):
            self.pattern = pattern

        def __hash__(self):
            return id(self)

        def __eq__(self, _other):
            return False

    def first_step(_ctx, **_kwargs):
        return None

    def second_step(_ctx, **_kwargs):
        return None

    registry = StepRegistry()
    registry._steps = {
        FakePattern("a duplicate step"): first_step,
        FakePattern("a duplicate step"): second_step,
    }
    custom = CustomStepManager()

    gen = behave_integration.BehaveStepsGenerator()
    steps_path = gen.generate(registry, custom, tmp_path)

    content = steps_path.read_text()
    assert content.count("@step('a duplicate step')") == 1


def test_setup_behave_directory_creates_temp_dir(tmp_path: Path):
    feature = ParsedFeature(
        name="Temp Feature",
        scenarios=[ParsedScenario(name="S", steps=[ParsedStep(keyword="Given", message="x")])],
    )
    registry = StepRegistry()
    registry.register(r"a step", lambda *args, **kwargs: None)
    custom = CustomStepManager()

    work_dir = behave_integration.setup_behave_directory(
        parsed_feature=feature,
        step_registry=registry,
        custom_steps=custom,
        procedure_file=tmp_path / "proc.tac",
        work_dir=None,
    )

    assert work_dir.exists()
    assert "tactus_behave_" in work_dir.name


def test_feature_generator_uses_explicit_filename(tmp_path: Path):
    feature = ParsedFeature(
        name="Explicit Name",
        scenarios=[ParsedScenario(name="S", steps=[ParsedStep(keyword="Given", message="x")])],
    )
    gen = behave_integration.BehaveFeatureGenerator()
    path = gen.generate(feature, tmp_path, filename="explicit.feature")

    assert path.name == "explicit.feature"
