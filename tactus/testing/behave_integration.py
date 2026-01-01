"""
Behave integration layer for Tactus BDD testing.

Generates Behave-compatible .feature files and step definitions
from parsed Gherkin and registered steps.
"""

import logging
import tempfile
from pathlib import Path
from typing import Dict, Optional

from .models import ParsedFeature, ParsedScenario
from .steps.registry import StepRegistry
from .steps.custom import CustomStepManager


logger = logging.getLogger(__name__)


class BehaveFeatureGenerator:
    """
    Generates Behave-compatible .feature files from parsed Gherkin.
    """

    def generate(
        self,
        parsed_feature: ParsedFeature,
        output_dir: Path,
        filename: Optional[str] = None,
    ) -> Path:
        """
        Generate .feature file from parsed Gherkin.

        Args:
            parsed_feature: Parsed Gherkin feature
            output_dir: Directory to write feature file
            filename: Optional custom filename (defaults to feature name)

        Returns:
            Path to generated feature file
        """
        if not filename:
            # Sanitize feature name for filename
            filename = parsed_feature.name.lower().replace(" ", "_") + ".feature"

        feature_file = output_dir / filename

        with open(feature_file, "w") as f:
            # Write feature header
            if parsed_feature.tags:
                for tag in parsed_feature.tags:
                    f.write(f"@{tag}\n")

            f.write(f"Feature: {parsed_feature.name}\n")

            if parsed_feature.description:
                # Indent description
                for line in parsed_feature.description.split("\n"):
                    f.write(f"  {line}\n")
                f.write("\n")

            # Write scenarios
            for scenario in parsed_feature.scenarios:
                self._write_scenario(f, scenario)

        logger.info(f"Generated feature file: {feature_file}")
        return feature_file

    def _write_scenario(self, f, scenario: ParsedScenario) -> None:
        """Write a scenario to the feature file."""
        # Write scenario tags
        if scenario.tags:
            f.write("  ")
            for tag in scenario.tags:
                f.write(f"@{tag} ")
            f.write("\n")

        # Add tag for filtering by scenario name
        sanitized_name = scenario.name.lower().replace(" ", "_")
        f.write(f"  @scenario_{sanitized_name}\n")

        f.write(f"  Scenario: {scenario.name}\n")

        # Write steps
        for step in scenario.steps:
            f.write(f"    {step.keyword} {step.text}\n")

        f.write("\n")


class BehaveStepsGenerator:
    """
    Generates Python step definitions for Behave.
    """

    def generate(
        self,
        step_registry: StepRegistry,
        custom_steps: CustomStepManager,
        output_dir: Path,
    ) -> Path:
        """
        Generate step_definitions.py for Behave.

        Args:
            step_registry: Registry of built-in steps
            custom_steps: Manager for custom Lua steps
            output_dir: Directory to write steps file

        Returns:
            Path to generated steps file
        """
        steps_dir = output_dir / "steps"
        steps_dir.mkdir(exist_ok=True)

        # Use unique filename based on output_dir to prevent conflicts
        import hashlib

        dir_hash = hashlib.md5(str(output_dir).encode()).hexdigest()[:8]
        steps_file = steps_dir / f"tactus_steps_{dir_hash}.py"

        with open(steps_file, "w") as f:
            # Write imports
            f.write("from behave import step, use_step_matcher\n")
            f.write("import sys\n")
            f.write("from pathlib import Path\n\n")

            # Use parse matcher instead of regex
            f.write("# Use parse matcher for simpler patterns\n")
            f.write("use_step_matcher('parse')\n\n")

            # Add tactus to path
            f.write("# Add tactus to path\n")
            f.write("sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))\n\n")

            # Import all built-in step functions
            f.write("from tactus.testing.steps import builtin\n")
            f.write("from tactus.testing.context import TactusTestContext\n")
            f.write("# Import mock steps for dependency mocking\n")
            f.write("from tactus.testing.steps import mock_steps\n\n")

            # Generate decorators for each built-in step pattern
            # Map pattern to actual function (avoid duplicates)
            pattern_to_func = {}
            for pattern, func in step_registry._steps.items():
                # Use pattern string as key to avoid duplicates
                pattern_str = pattern.pattern
                if pattern_str not in pattern_to_func:
                    pattern_to_func[pattern_str] = func.__name__

            for pattern_str, func_name in pattern_to_func.items():
                # Create a unique wrapper function name
                wrapper_name = self._pattern_to_func_name(pattern_str)

                # Convert regex pattern to parse pattern
                # Replace (?P<name>...) with {name}
                parse_pattern = self._regex_to_parse_pattern(pattern_str)

                # Escape quotes in pattern for Python string
                escaped_pattern = parse_pattern.replace("'", "\\'").replace('"', '\\"')

                # Use @step() decorator which works for Given/When/Then/And/But
                # This prevents duplicate step definition errors
                f.write(f"@step('{escaped_pattern}')\n")
                f.write(f"def {wrapper_name}(context, **kwargs):\n")
                f.write(f'    """Step: {escaped_pattern[:60]}"""\n')
                f.write("    # Call the actual step function from builtin module\n")
                f.write(f"    builtin.{func_name}(context.tac, **kwargs)\n\n")

        logger.info(f"Generated steps file: {steps_file}")
        return steps_file

    def _regex_to_parse_pattern(self, regex_pattern: str) -> str:
        """Convert regex pattern to parse pattern."""
        import re

        # Replace (?P<name>\w+) with {name:w}
        pattern = re.sub(r"\(\?P<(\w+)>\\w\+\)", r"{\1:w}", regex_pattern)
        # Replace (?P<name>\d+) with {name:d}
        pattern = re.sub(r"\(\?P<(\w+)>\\d\+\)", r"{\1:d}", pattern)
        # Replace (?P<name>.+) with {name}
        pattern = re.sub(r"\(\?P<(\w+)>\.\+\)", r"{\1}", pattern)
        return pattern

    def _pattern_to_func_name(self, pattern: str) -> str:
        """Convert regex pattern to valid Python function name."""
        import re
        import hashlib

        # Remove regex special characters and convert to snake_case
        name = re.sub(r"[^a-zA-Z0-9_]", "_", pattern)
        name = re.sub(r"_+", "_", name)  # Collapse multiple underscores
        name = name.strip("_")
        # Add hash to make unique across different temp directories
        pattern_hash = hashlib.md5(pattern.encode()).hexdigest()[:8]
        return f"step_{name[:40]}_{pattern_hash}"  # Limit length + unique hash


class BehaveEnvironmentGenerator:
    """
    Generates environment.py for Behave with Tactus context setup.
    """

    def generate(
        self,
        output_dir: Path,
        procedure_file: Path,
        mock_tools: Optional[Dict] = None,
        params: Optional[Dict] = None,
        mocked: bool = False,
    ) -> Path:
        """
        Generate environment.py for Behave.

        Args:
            output_dir: Directory to write environment file
            procedure_file: Path to the procedure file being tested
            mock_tools: Optional dict of tool_name -> mock_response
            params: Optional dict of parameters to pass to procedure
            mocked: Whether to use mocked dependencies

        Returns:
            Path to generated environment file
        """
        env_file = output_dir / "environment.py"

        # Serialize mock_tools and params for embedding
        import json

        mock_tools_json = json.dumps(mock_tools or {}).replace("'", "\\'")
        params_json = json.dumps(params or {}).replace("'", "\\'")

        # Convert procedure_file to absolute path so it works from temp behave directory
        absolute_procedure_file = Path(procedure_file).resolve()

        with open(env_file, "w") as f:
            f.write('"""\n')
            f.write("Behave environment for Tactus BDD testing.\n")
            f.write('"""\n\n')

            f.write("import sys\n")
            f.write("import json\n")
            f.write("from pathlib import Path\n\n")

            f.write("# Add tactus to path\n")
            f.write("sys.path.insert(0, str(Path(__file__).parent.parent.parent))\n\n")

            f.write("from tactus.testing.context import TactusTestContext\n")
            f.write("from tactus.testing.steps.registry import StepRegistry\n")
            f.write("from tactus.testing.steps.builtin import register_builtin_steps\n")
            f.write("from tactus.testing.steps.custom import CustomStepManager\n\n")

            f.write("def before_all(context):\n")
            f.write('    """Setup before all tests."""\n')
            f.write("    # Initialize step registry\n")
            f.write("    context.step_registry = StepRegistry()\n")
            f.write("    register_builtin_steps(context.step_registry)\n")
            f.write("    \n")
            f.write("    # Initialize custom step manager\n")
            f.write("    context.custom_steps = CustomStepManager()\n")
            f.write("    \n")
            f.write("    # Store test configuration (using absolute path)\n")
            f.write(f"    context.procedure_file = Path(r'{absolute_procedure_file}')\n")
            f.write(f"    context.mock_tools = json.loads('{mock_tools_json}')\n")
            f.write(f"    context.params = json.loads('{params_json}')\n")
            f.write(f"    context.mocked = {mocked}\n\n")

            f.write("def before_scenario(context, scenario):\n")
            f.write('    """Setup before each scenario."""\n')
            f.write("    # Import mock registry for dependency mocking\n")
            f.write("    from tactus.testing.mock_registry import UnifiedMockRegistry\n")
            f.write("    from tactus.testing.mock_hitl import MockHITLHandler\n")
            f.write("    \n")
            f.write("    # Create fresh Tactus context for each scenario\n")
            f.write("    context.tac = TactusTestContext(\n")
            f.write("        procedure_file=context.procedure_file,\n")
            f.write("        params=context.params,\n")
            f.write("        mock_tools=context.mock_tools,\n")
            f.write("        mocked=context.mocked,\n")
            f.write("    )\n")
            f.write("    \n")
            f.write("    # Create mock registry for Gherkin steps to configure\n")
            f.write("    if context.mocked:\n")
            f.write(
                "        context.mock_registry = UnifiedMockRegistry(hitl_handler=MockHITLHandler())\n"
            )
            f.write("        # Share mock registry with TactusTestContext\n")
            f.write("        context.tac.mock_registry = context.mock_registry\n\n")

            f.write("def after_scenario(context, scenario):\n")
            f.write('    """Cleanup after each scenario."""\n')
            f.write("    # Attach execution metrics to scenario for reporting\n")
            f.write("    if hasattr(context, 'tac') and context.tac:\n")
            f.write("        scenario.total_cost = getattr(context.tac, 'total_cost', 0.0)\n")
            f.write("        scenario.total_tokens = getattr(context.tac, 'total_tokens', 0)\n")
            f.write(
                "        scenario.cost_breakdown = getattr(context.tac, 'cost_breakdown', [])\n"
            )
            f.write("        scenario.iterations = getattr(context.tac, 'iterations', 0)\n")
            f.write("        scenario.tools_used = getattr(context.tac, 'tools_used', [])\n")
            f.write("    # Cleanup runtime if it was created\n")
            f.write("    if hasattr(context.tac, 'runtime') and context.tac.runtime:\n")
            f.write("        # Any cleanup needed\n")
            f.write("        pass\n")

        logger.info(f"Generated environment file: {env_file}")
        return env_file


def setup_behave_directory(
    parsed_feature: ParsedFeature,
    step_registry: StepRegistry,
    custom_steps: CustomStepManager,
    procedure_file: Path,
    work_dir: Optional[Path] = None,
    mock_tools: Optional[Dict] = None,
    params: Optional[Dict] = None,
    mocked: bool = False,
) -> Path:
    """
    Setup complete Behave directory structure.

    Args:
        parsed_feature: Parsed Gherkin feature
        step_registry: Registry of built-in steps
        custom_steps: Custom step manager
        procedure_file: Path to procedure file being tested
        work_dir: Optional work directory (creates temp if not provided)
        mock_tools: Optional dict of tool mocks
        params: Optional dict of procedure parameters
        mocked: Whether to use mocked dependencies

    Returns:
        Path to Behave work directory
    """
    if work_dir is None:
        # Always create a unique temp directory
        work_dir = Path(tempfile.mkdtemp(prefix="tactus_behave_"))
    else:
        work_dir.mkdir(parents=True, exist_ok=True)

    # Generate feature file
    feature_gen = BehaveFeatureGenerator()
    feature_gen.generate(parsed_feature, work_dir)

    # Generate step definitions
    steps_gen = BehaveStepsGenerator()
    steps_gen.generate(step_registry, custom_steps, work_dir)

    # Generate environment.py with mock tools, params, and mocked flag
    env_gen = BehaveEnvironmentGenerator()
    env_gen.generate(work_dir, procedure_file, mock_tools, params, mocked)

    logger.info(f"Behave directory setup complete: {work_dir}")
    return work_dir
