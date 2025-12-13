"""
Test runner for Tactus BDD testing.

Runs tests with parallel scenario execution using multiprocessing.
"""

import importlib.util
import logging
import os
from datetime import datetime
from multiprocessing import Pool
from pathlib import Path
from typing import Dict, List, Optional

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
    ):
        if not BEHAVE_AVAILABLE:
            raise ImportError("behave library not installed. " "Install with: pip install behave")

        self.procedure_file = procedure_file
        self.mock_tools = mock_tools or {}
        self.params = params or {}
        self.work_dir: Optional[Path] = None
        self.parsed_feature: Optional[ParsedFeature] = None
        self.step_registry = StepRegistry()
        self.custom_steps = CustomStepManager()

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

        # Setup Behave directory with mock tools and params
        self.work_dir = setup_behave_directory(
            self.parsed_feature,
            self.step_registry,
            self.custom_steps,
            self.procedure_file,
            mock_tools=self.mock_tools,
            params=self.params,
        )

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
            # Run in parallel
            with Pool(processes=min(len(scenarios), os.cpu_count() or 1)) as pool:
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
        Run a single scenario (called in subprocess).

        Note: Clears Behave's global step registry to prevent conflicts
        when running multiple tests in the same process.

        Args:
            scenario_name: Name of scenario to run
            work_dir: Path to Behave work directory

        Returns:
            ScenarioResult
        """
        from behave.runner import Runner
        from behave.configuration import Configuration

        # Create tag filter for this scenario
        sanitized_name = scenario_name.lower().replace(" ", "_")
        tag_filter = f"scenario_{sanitized_name}"

        # Configure Behave
        config = Configuration(
            command_args=[str(work_dir)],
            tags=[tag_filter],
            format=["null"],  # Suppress output
            show_timings=True,
        )
        # Prevent behave from searching parent directories for step files
        work_dir = Path(work_dir)  # Ensure Path object
        config.paths = [str(work_dir)]
        # Explicitly set step_paths to only this work_dir
        config.step_paths = [str(work_dir / "steps")]

        # Run Behave
        runner = Runner(config)
        runner.run()

        # Extract results from Behave
        for feature in runner.features:
            for scenario in feature.scenarios:
                if scenario.name == scenario_name:
                    return TactusTestRunner._convert_scenario_result(scenario)

        # Scenario not found (shouldn't happen)
        raise RuntimeError(f"Scenario '{scenario_name}' not found in Behave results")

    @staticmethod
    def _convert_scenario_result(behave_scenario) -> ScenarioResult:
        """Convert Behave scenario to ScenarioResult."""
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
        iterations = getattr(behave_scenario, "iterations", 0)
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
        """Cleanup temporary files."""
        if self.work_dir and self.work_dir.exists():
            import shutil

            try:
                shutil.rmtree(self.work_dir)
                logger.debug(f"Cleaned up work directory: {self.work_dir}")
            except Exception as e:
                logger.warning(f"Failed to cleanup work directory: {e}")
