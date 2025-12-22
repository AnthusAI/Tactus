"""
Evaluation runner for Tactus BDD testing.

Runs scenarios multiple times in parallel to measure consistency and reliability.
"""

import logging
import os
import statistics
import multiprocessing
from collections import Counter
from typing import List

from .models import ScenarioResult, EvaluationResult
from .test_runner import TactusTestRunner


logger = logging.getLogger(__name__)


class TactusEvaluationRunner(TactusTestRunner):
    """
    Runs Tactus BDD evaluations with multiple iterations per scenario.

    Extends TactusTestRunner to run scenarios multiple times and
    calculate consistency and reliability metrics.
    """

    def evaluate_all(
        self,
        runs: int = 10,
        parallel: bool = True,
    ) -> List[EvaluationResult]:
        """
        Evaluate all scenarios with N runs each.

        Args:
            runs: Number of times to run each scenario
            parallel: Whether to run iterations in parallel

        Returns:
            List of EvaluationResult, one per scenario
        """
        if not self.parsed_feature or not self.work_dir:
            raise RuntimeError("Must call setup() before evaluate_all()")

        results = []
        for scenario in self.parsed_feature.scenarios:
            eval_result = self._evaluate_scenario(
                scenario.name,
                runs,
                parallel,
            )
            results.append(eval_result)

        return results

    def evaluate_scenario(
        self,
        scenario_name: str,
        runs: int = 10,
        parallel: bool = True,
    ) -> EvaluationResult:
        """
        Evaluate a single scenario with N runs.

        Args:
            scenario_name: Name of scenario to evaluate
            runs: Number of times to run the scenario
            parallel: Whether to run iterations in parallel

        Returns:
            EvaluationResult with consistency metrics
        """
        if not self.work_dir:
            raise RuntimeError("Must call setup() before evaluate_scenario()")

        return self._evaluate_scenario(scenario_name, runs, parallel)

    def _evaluate_scenario(
        self,
        scenario_name: str,
        runs: int,
        parallel: bool,
    ) -> EvaluationResult:
        """
        Run single scenario N times and calculate metrics.

        Args:
            scenario_name: Name of scenario to evaluate
            runs: Number of iterations
            parallel: Whether to run in parallel

        Returns:
            EvaluationResult with all metrics
        """
        logger.info(f"Evaluating scenario '{scenario_name}' with {runs} runs")

        # Run scenario N times
        if parallel:
            workers = min(runs, os.cpu_count() or 1)
            # Use 'spawn' to avoid Behave global state conflicts
            ctx = multiprocessing.get_context("spawn")
            with ctx.Pool(processes=workers) as pool:
                iteration_args = [(scenario_name, str(self.work_dir), i) for i in range(runs)]
                results = pool.starmap(self._run_single_iteration, iteration_args)
        else:
            results = [
                self._run_single_iteration(scenario_name, str(self.work_dir), i)
                for i in range(runs)
            ]

        # Calculate metrics
        return self._calculate_metrics(scenario_name, results)

    @staticmethod
    def _run_single_iteration(
        scenario_name: str,
        work_dir: str,
        iteration: int,
    ) -> ScenarioResult:
        """
        Run one iteration of a scenario (called in subprocess).

        Args:
            scenario_name: Name of scenario to run
            work_dir: Path to Behave work directory
            iteration: Iteration number (for tracking)

        Returns:
            ScenarioResult with iteration number
        """
        result = TactusTestRunner._run_single_scenario(scenario_name, work_dir)
        result.iteration = iteration
        return result

    def _calculate_metrics(
        self,
        scenario_name: str,
        results: List[ScenarioResult],
    ) -> EvaluationResult:
        """
        Calculate consistency and reliability metrics.

        Args:
            scenario_name: Name of scenario
            results: List of ScenarioResult from all runs

        Returns:
            EvaluationResult with all metrics
        """
        total_runs = len(results)
        passed_runs = sum(1 for r in results if r.status == "passed")
        failed_runs = total_runs - passed_runs

        # Success rate
        success_rate = passed_runs / total_runs if total_runs > 0 else 0.0

        # Timing statistics
        durations = [r.duration for r in results]
        mean_duration = statistics.mean(durations) if durations else 0.0
        median_duration = statistics.median(durations) if durations else 0.0
        stddev_duration = statistics.stdev(durations) if len(durations) > 1 else 0.0

        # Consistency score - compare step outcomes
        consistency_score = self._calculate_consistency(results)

        # Flakiness detection
        is_flaky = 0 < passed_runs < total_runs

        logger.info(
            f"Scenario '{scenario_name}': "
            f"Success rate: {success_rate:.1%}, "
            f"Consistency: {consistency_score:.1%}, "
            f"Flaky: {is_flaky}"
        )

        return EvaluationResult(
            scenario_name=scenario_name,
            total_runs=total_runs,
            passed_runs=passed_runs,
            failed_runs=failed_runs,
            success_rate=success_rate,
            mean_duration=mean_duration,
            median_duration=median_duration,
            stddev_duration=stddev_duration,
            consistency_score=consistency_score,
            is_flaky=is_flaky,
            individual_results=results,
        )

    def _calculate_consistency(self, results: List[ScenarioResult]) -> float:
        """
        Calculate consistency by comparing step outcomes.

        Consistency score measures how often the scenario produces
        identical step-by-step behavior across runs.

        1.0 = all runs had identical step outcomes
        0.0 = completely inconsistent

        Args:
            results: List of ScenarioResult

        Returns:
            Consistency score between 0.0 and 1.0
        """
        if not results:
            return 0.0

        # Create signature for each run (step statuses)
        signatures = []
        for result in results:
            sig = tuple((step.keyword, step.text, step.status) for step in result.steps)
            signatures.append(sig)

        # Count most common signature
        signature_counts = Counter(signatures)
        most_common_count = signature_counts.most_common(1)[0][1]

        # Consistency is the fraction of runs that match the most common pattern
        return most_common_count / len(results)
