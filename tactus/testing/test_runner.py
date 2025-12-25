"""
Test runner for Tactus BDD testing.

Runs tests with parallel scenario execution using multiprocessing.
"""

import importlib.util
import logging
import os
import sys
import subprocess
import multiprocessing
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from .models import (
    ParsedFeature,
    ScenarioResult,
    StepResult,
    FeatureResult,
    TestResult,
)
from .gherkin_parser import GherkinParser
from .behave_integration import setup_behave_directory
from .steps.registry import StepRegistry
from .steps.builtin import register_builtin_steps
from .steps.custom import CustomStepManager

BEHAVE_AVAILABLE = importlib.util.find_spec("behave") is not None


logger = logging.getLogger(__name__)


class TactusTestRunner:
    """
    Runs Tactus BDD tests with parallel scenario execution.

    Parses Gherkin specifications, generates Behave files,
    and executes scenarios in parallel for performance.
    """

    def __init__(
        self,
        procedure_file: Path,
        mock_tools: Optional[Dict] = None,
        params: Optional[Dict] = None,
        mocked: bool = False,
    ):
        if not BEHAVE_AVAILABLE:
            raise ImportError("behave library not installed. " "Install with: pip install behave")

        self.procedure_file = procedure_file
        self.mock_tools = mock_tools or {}
        self.params = params or {}
        self.mocked = mocked  # Whether to use mocked dependencies
        self.work_dir: Optional[Path] = None
        self.parsed_feature: Optional[ParsedFeature] = None
        self.step_registry = StepRegistry()
        self.custom_steps = CustomStepManager()
        self.generated_step_file: Optional[Path] = None

        # Register built-in steps
        register_builtin_steps(self.step_registry)

    def setup(self, gherkin_text: str) -> None:
        """
        Setup test environment from Gherkin text.

        Args:
            gherkin_text: Raw Gherkin feature text
        """
        # Parse Gherkin
        parser = GherkinParser()
        self.parsed_feature = parser.parse(gherkin_text)

        # Setup Behave directory with mock tools, params, and mocked flag
        self.work_dir = setup_behave_directory(
            self.parsed_feature,
            self.step_registry,
            self.custom_steps,
            self.procedure_file,
            mock_tools=self.mock_tools,
            params=self.params,
            mocked=self.mocked,
        )

        # Track the generated step file for cleanup
        # The step file name is based on the work_dir hash
        import hashlib

        dir_hash = hashlib.md5(str(self.work_dir).encode()).hexdigest()[:8]
        self.generated_step_file = self.work_dir / "steps" / f"tactus_steps_{dir_hash}.py"

        logger.info(f"Test setup complete for feature: {self.parsed_feature.name}")

    def run_tests(self, parallel: bool = True, scenario_filter: Optional[str] = None) -> TestResult:
        """
        Run all scenarios (optionally in parallel).

        Args:
            parallel: Whether to run scenarios in parallel
            scenario_filter: Optional scenario name to run (runs only that scenario)

        Returns:
            TestResult with all scenario results
        """
        if not self.parsed_feature or not self.work_dir:
            raise RuntimeError("Must call setup() before run_tests()")

        # Get scenarios to run
        scenarios = self.parsed_feature.scenarios
        if scenario_filter:
            scenarios = [s for s in scenarios if s.name == scenario_filter]
            if not scenarios:
                raise ValueError(f"Scenario not found: {scenario_filter}")

        # Run scenarios
        if parallel and len(scenarios) > 1:
            # Run in parallel using 'spawn' to avoid Behave global state conflicts
            # 'spawn' creates fresh Python interpreters for each worker
            ctx = multiprocessing.get_context("spawn")
            with ctx.Pool(processes=min(len(scenarios), os.cpu_count() or 1)) as pool:
                scenario_results = pool.starmap(
                    self._run_single_scenario, [(s.name, str(self.work_dir)) for s in scenarios]
                )
        else:
            # Run sequentially
            scenario_results = [
                self._run_single_scenario(s.name, str(self.work_dir)) for s in scenarios
            ]

        # Build feature result
        feature_result = self._build_feature_result(scenario_results)

        # Build test result
        return self._build_test_result([feature_result])

    @staticmethod
    def _run_single_scenario(scenario_name: str, work_dir: str) -> ScenarioResult:
        """
        Run a single scenario in subprocess to avoid event loop conflicts.

        Args:
            scenario_name: Name of scenario to run
            work_dir: Path to Behave work directory

        Returns:
            ScenarioResult
        """
        # Create tag filter for this scenario
        sanitized_name = scenario_name.lower().replace(" ", "_")
        tag_filter = f"scenario_{sanitized_name}"

        # Run behave in subprocess to isolate event loops
        cmd = [
            sys.executable,
            "-m",
            "behave",
            str(work_dir),
            "--tags",
            tag_filter,
            "--no-capture",
            "--format",
            "json",
            "--outfile",
            f"{work_dir}/results.json",
        ]

        logger.debug(f"Running behave subprocess: {' '.join(cmd)}")

        try:
            # Ensure tactus module is importable in subprocess
            env = os.environ.copy()
            # Add parent directory to PYTHONPATH so tactus can be imported
            project_root = Path(__file__).parent.parent.parent  # Go up to project root
            if "PYTHONPATH" in env:
                env["PYTHONPATH"] = f"{project_root}:{env['PYTHONPATH']}"
            else:
                env["PYTHONPATH"] = str(project_root)

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=600,  # 10 minute timeout
                cwd=work_dir,
                env=env,
            )

            # Check if behave ran successfully (even if tests failed)
            if result.returncode not in [0, 1]:
                # Return code 0 = all passed, 1 = some failed, other = error
                raise RuntimeError(
                    f"Behave subprocess failed with return code {result.returncode}\n"
                    f"STDOUT: {result.stdout}\n"
                    f"STDERR: {result.stderr}"
                )

            # Parse JSON results
            import json

            results_file = Path(work_dir) / "results.json"
            if not results_file.exists():
                raise RuntimeError(
                    f"Behave results file not found: {results_file}\n"
                    f"Return code: {result.returncode}\n"
                    f"STDOUT: {result.stdout}\n"
                    f"STDERR: {result.stderr}"
                )

            # Behave may write multiple JSON objects (one per feature run)
            # We need to parse them separately and combine
            with open(results_file) as f:
                content = f.read().strip()
                if not content:
                    raise RuntimeError("Behave results file is empty")

                # Try to parse as single JSON first
                try:
                    behave_results = json.loads(content)
                except json.JSONDecodeError:
                    # Multiple JSON objects - split and parse each
                    behave_results = []
                    for line in content.split("\n"):
                        line = line.strip()
                        if line:
                            try:
                                obj = json.loads(line)
                                if isinstance(obj, list):
                                    behave_results.extend(obj)
                                else:
                                    behave_results.append(obj)
                            except json.JSONDecodeError:
                                continue

            # Extract the scenario result
            for feature_data in behave_results:
                for element in feature_data.get("elements", []):
                    if element.get("name") == scenario_name:
                        return TactusTestRunner._convert_json_scenario_result(element)

            # Scenario not found (shouldn't happen)
            raise RuntimeError(f"Scenario '{scenario_name}' not found in Behave JSON results")

        except subprocess.TimeoutExpired:
            raise RuntimeError(f"Scenario '{scenario_name}' timed out after 10 minutes")
        except Exception as e:
            logger.error(f"Error running scenario '{scenario_name}': {e}", exc_info=True)
            raise

    @staticmethod
    def _convert_json_scenario_result(scenario_data: Dict[str, Any]) -> ScenarioResult:
        """Convert Behave JSON scenario data to ScenarioResult."""
        steps = []
        for step_data in scenario_data.get("steps", []):
            result = step_data.get("result", {})
            steps.append(
                StepResult(
                    keyword=step_data.get("keyword", ""),
                    text=step_data.get("name", ""),
                    status=result.get("status", "skipped"),
                    duration=result.get("duration", 0.0),
                    error_message=result.get("error_message"),
                )
            )

        # Calculate total duration from steps
        total_duration = sum(s.duration for s in steps)

        # Extract tags
        tags = [tag.replace("@", "") for tag in scenario_data.get("tags", [])]

        # Extract execution metrics from scenario properties (if attached by hook)
        # These would be in the scenario_data dict if the hook sets them
        total_cost = scenario_data.get("total_cost", 0.0)
        total_tokens = scenario_data.get("total_tokens", 0)
        iterations = scenario_data.get("iterations", 0)
        tools_used = scenario_data.get("tools_used", [])
        llm_calls = scenario_data.get("llm_calls", 0)

        # Determine overall status
        status = scenario_data.get("status", "passed")

        return ScenarioResult(
            name=scenario_data.get("name", ""),
            status=status,
            duration=total_duration,
            steps=steps,
            tags=tags,
            timestamp=datetime.now(),
            total_cost=total_cost,
            total_tokens=total_tokens,
            iterations=iterations,
            tools_used=tools_used,
            llm_calls=llm_calls,
        )

    @staticmethod
    def _convert_scenario_result(behave_scenario) -> ScenarioResult:
        """Convert Behave scenario object to ScenarioResult (legacy method)."""
        steps = []
        for behave_step in behave_scenario.steps:
            steps.append(
                StepResult(
                    keyword=behave_step.keyword,
                    text=behave_step.name,
                    status=behave_step.status.name,
                    duration=behave_step.duration,
                    error_message=(
                        behave_step.error_message if hasattr(behave_step, "error_message") else None
                    ),
                )
            )

        # Extract execution metrics (attached by after_scenario hook)
        total_cost = getattr(behave_scenario, "total_cost", 0.0)
        total_tokens = getattr(behave_scenario, "total_tokens", 0)
        cost_breakdown = getattr(behave_scenario, "cost_breakdown", [])
        # iterations is a method, not an attribute - call it if it exists
        iterations_attr = getattr(behave_scenario, "iterations", None)
        iterations = iterations_attr() if callable(iterations_attr) else 0
        tools_used = getattr(behave_scenario, "tools_used", [])
        llm_calls = len(cost_breakdown)  # Number of LLM calls = number of cost events

        return ScenarioResult(
            name=behave_scenario.name,
            status=behave_scenario.status.name,
            duration=behave_scenario.duration,
            steps=steps,
            tags=behave_scenario.tags,
            timestamp=datetime.now(),
            total_cost=total_cost,
            total_tokens=total_tokens,
            iterations=iterations,
            tools_used=tools_used,
            llm_calls=llm_calls,
        )

    def _build_feature_result(self, scenario_results: List[ScenarioResult]) -> FeatureResult:
        """Build FeatureResult from scenario results."""
        if not self.parsed_feature:
            raise RuntimeError("No parsed feature available")

        # Calculate feature status
        all_passed = all(s.status == "passed" for s in scenario_results)
        any_failed = any(s.status == "failed" for s in scenario_results)
        status = "passed" if all_passed else ("failed" if any_failed else "skipped")

        # Calculate total duration
        total_duration = sum(s.duration for s in scenario_results)

        return FeatureResult(
            name=self.parsed_feature.name,
            description=self.parsed_feature.description,
            status=status,
            duration=total_duration,
            scenarios=scenario_results,
            tags=self.parsed_feature.tags,
        )

    def _build_test_result(self, feature_results: List[FeatureResult]) -> TestResult:
        """Build TestResult from feature results."""
        total_scenarios = sum(len(f.scenarios) for f in feature_results)
        passed_scenarios = sum(
            1 for f in feature_results for s in f.scenarios if s.status == "passed"
        )
        failed_scenarios = total_scenarios - passed_scenarios
        total_duration = sum(f.duration for f in feature_results)

        # Aggregate execution metrics across all scenarios
        total_cost = sum(s.total_cost for f in feature_results for s in f.scenarios)
        total_tokens = sum(s.total_tokens for f in feature_results for s in f.scenarios)
        total_iterations = sum(s.iterations for f in feature_results for s in f.scenarios)
        total_llm_calls = sum(s.llm_calls for f in feature_results for s in f.scenarios)

        # Collect unique tools used across all scenarios
        all_tools = set()
        for f in feature_results:
            for s in f.scenarios:
                all_tools.update(s.tools_used)
        unique_tools_used = sorted(list(all_tools))

        return TestResult(
            features=feature_results,
            total_scenarios=total_scenarios,
            passed_scenarios=passed_scenarios,
            failed_scenarios=failed_scenarios,
            total_duration=total_duration,
            total_cost=total_cost,
            total_tokens=total_tokens,
            total_iterations=total_iterations,
            total_llm_calls=total_llm_calls,
            unique_tools_used=unique_tools_used,
        )

    def cleanup(self) -> None:
        """
        Cleanup temporary files and clear Behave state.

        This removes:
        - The temporary work directory
        - Generated step modules from sys.modules
        - Behave's global step registry
        """
        import sys
        import importlib

        # Clear the generated step module from sys.modules
        if self.generated_step_file:
            # Compute the module name that Python would use
            # The step file is in work_dir/steps/tactus_steps_<hash>.py
            # Python imports it as "steps.tactus_steps_<hash>"
            step_module_name = f"steps.{self.generated_step_file.stem}"

            # Remove all variations of this module name
            modules_to_clear = [
                m
                for m in list(sys.modules.keys())
                if step_module_name in m or self.generated_step_file.stem in m
            ]

            for mod in modules_to_clear:
                del sys.modules[mod]
                logger.debug(f"Cleared module from sys.modules: {mod}")

        # Clear Behave's global step registry IN-PLACE
        # IMPORTANT: We call registry.clear() instead of creating a new registry
        # because the @step decorator has a closure reference to the registry object.
        try:
            import behave.step_registry

            behave.step_registry.registry.clear()
            logger.debug("Cleared Behave step registry")
        except ImportError:
            pass

        # Invalidate import caches
        importlib.invalidate_caches()

        # Clean up work directory
        if self.work_dir and self.work_dir.exists():
            import shutil

            try:
                shutil.rmtree(self.work_dir)
                logger.debug(f"Cleaned up work directory: {self.work_dir}")
            except Exception as e:
                logger.warning(f"Failed to cleanup work directory: {e}")
