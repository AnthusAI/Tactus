"""
Pydantic Evals runner for Tactus procedures.

This module bridges Tactus procedures to the Pydantic Evals framework,
allowing evaluation of LLM agent quality, consistency, and performance.
"""

import asyncio
import logging
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, TYPE_CHECKING

from .eval_models import EvaluationConfig, EvalCase

if TYPE_CHECKING:  # pragma: no cover
    from tactus.core.runtime import TactusRuntime

logger = logging.getLogger(__name__)

# Check if pydantic_evals is available
try:
    from pydantic_evals import Dataset
    from pydantic_evals.evaluators import Evaluator

    PYDANTIC_EVALS_AVAILABLE = True
except ImportError:
    PYDANTIC_EVALS_AVAILABLE = False
    logger.warning("pydantic_evals not installed. Install with: pip install pydantic-evals")


class TactusPydanticEvalRunner:
    """
    Runs Pydantic Evals on Tactus procedures.

    Converts Tactus evaluation config to Pydantic Evals Dataset,
    executes procedure as the "task", and collects results.
    """

    def __init__(
        self,
        procedure_file: Path,
        eval_config: EvaluationConfig,
        openai_api_key: Optional[str] = None,
    ):
        """
        Initialize the evaluation runner.

        Args:
            procedure_file: Path to the .tac procedure file
            eval_config: Evaluation configuration from evaluations() block
            openai_api_key: Optional OpenAI API key for LLM calls
        """
        if not PYDANTIC_EVALS_AVAILABLE:
            raise ImportError(
                "pydantic_evals is required for evaluations. "
                "Install with: pip install pydantic-evals"
            )

        self.procedure_file = procedure_file
        self.eval_config = eval_config
        self.openai_api_key = openai_api_key
        self._procedure_source: Optional[str] = None

    def run_evaluation(self):
        """
        Run evaluation using Pydantic Evals framework.

        Flow:
        1. Convert eval_config to pydantic_evals.Dataset
        2. Create task function that runs Tactus procedure
        3. Execute dataset.evaluate_sync(task)
        4. Return EvaluationReport

        Returns:
            Pydantic Evals EvaluationReport
        """
        logger.info(f"Running evaluation on {self.procedure_file}")

        # Load procedure source once
        self._procedure_source = self.procedure_file.read_text()

        # Create Pydantic Evals dataset
        dataset = self._create_dataset()

        # Create task function
        task = self._create_task_function()

        # Run evaluation
        logger.info(f"Evaluating {len(self.eval_config.dataset)} cases...")
        report = dataset.evaluate_sync(task)

        logger.info("Evaluation complete")
        return report

    def _create_dataset(self) -> "Dataset":
        """
        Convert Tactus EvaluationConfig to Pydantic Evals Dataset.

        Returns:
            Pydantic Evals Dataset
        """
        from pydantic_evals import Case

        # Load cases from file if specified
        all_eval_cases = []
        if self.eval_config.dataset_file:
            all_eval_cases.extend(self._load_dataset_file(self.eval_config.dataset_file))

        # Add inline dataset cases
        all_eval_cases.extend(self.eval_config.dataset)

        # Convert cases - duplicate each case N times for multiple runs
        cases = []
        runs = self.eval_config.runs or 1

        for eval_case in all_eval_cases:
            for run_num in range(runs):
                # Create a unique name for each run
                case_name = eval_case.name
                if runs > 1:
                    case_name = f"{eval_case.name}_run{run_num + 1}"

                case = Case(
                    name=case_name,
                    inputs=eval_case.inputs,
                    expected_output=eval_case.expected_output,
                    metadata={
                        **eval_case.metadata,
                        "run_number": run_num + 1,
                        "original_case_name": eval_case.name,
                        # Trace will be populated during execution
                        "trace": {},
                    },
                )
                cases.append(case)

        # Convert evaluators
        evaluators = self._create_evaluators()

        # Create dataset
        dataset = Dataset(
            cases=cases,
            evaluators=evaluators,
        )

        return dataset

    def _load_dataset_file(self, dataset_file: str) -> List[EvalCase]:
        """
        Load evaluation cases from external file.

        Supports .jsonl, .json, and .csv formats.

        Args:
            dataset_file: Path to dataset file (relative to procedure file or absolute)

        Returns:
            List of EvalCase objects

        Raises:
            ValueError: If file format is unsupported
            FileNotFoundError: If file doesn't exist
        """
        from pathlib import Path

        # Resolve path
        file_path = Path(dataset_file)
        if not file_path.is_absolute():
            # Resolve relative to procedure file
            file_path = self.procedure_file.parent / file_path

        if not file_path.exists():
            raise FileNotFoundError(f"Dataset file not found: {file_path}")

        # Load based on file extension
        if file_path.suffix == ".jsonl":
            return self._load_jsonl(file_path)
        elif file_path.suffix == ".json":
            return self._load_json(file_path)
        elif file_path.suffix == ".csv":
            return self._load_csv(file_path)
        else:
            raise ValueError(
                f"Unsupported dataset file format: {file_path.suffix}. "
                f"Supported formats: .jsonl, .json, .csv"
            )

    def _load_jsonl(self, file_path: Path) -> List[EvalCase]:
        """Load cases from JSONL file (one JSON object per line)."""
        import json

        cases = []
        with open(file_path, "r", encoding="utf-8") as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    cases.append(EvalCase(**data))
                except json.JSONDecodeError as e:
                    raise ValueError(f"Invalid JSON on line {line_num} in {file_path}: {e}")
                except Exception as e:
                    raise ValueError(f"Invalid case data on line {line_num} in {file_path}: {e}")
        return cases

    def _load_json(self, file_path: Path) -> List[EvalCase]:
        """Load cases from JSON file (array of objects)."""
        import json

        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        if not isinstance(data, list):
            raise ValueError(f"JSON file must contain an array of cases: {file_path}")

        cases = []
        for idx, item in enumerate(data):
            try:
                cases.append(EvalCase(**item))
            except Exception as e:
                raise ValueError(f"Invalid case data at index {idx} in {file_path}: {e}")
        return cases

    def _load_csv(self, file_path: Path) -> List[EvalCase]:
        """
        Load cases from CSV file.

        Expected columns:
        - name: Case name (required)
        - inputs: JSON string of inputs dict (required)
        - expected_output: JSON string of expected output dict (optional)
        - metadata: JSON string of metadata dict (optional)
        """
        import csv
        import json

        cases = []
        with open(file_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)

            if not reader.fieldnames or "name" not in reader.fieldnames:
                raise ValueError(f"CSV must have 'name' column: {file_path}")
            if "inputs" not in reader.fieldnames:
                raise ValueError(f"CSV must have 'inputs' column: {file_path}")

            for row_num, row in enumerate(reader, 2):  # Start at 2 (header is 1)
                try:
                    # Parse required fields
                    name = row["name"]
                    inputs = json.loads(row["inputs"])

                    # Parse optional fields
                    expected_output = None
                    if "expected_output" in row and row["expected_output"]:
                        expected_output = json.loads(row["expected_output"])

                    metadata = {}
                    if "metadata" in row and row["metadata"]:
                        metadata = json.loads(row["metadata"])

                    cases.append(
                        EvalCase(
                            name=name,
                            inputs=inputs,
                            expected_output=expected_output,
                            metadata=metadata,
                        )
                    )
                except json.JSONDecodeError as e:
                    raise ValueError(f"Invalid JSON in row {row_num} of {file_path}: {e}")
                except Exception as e:
                    raise ValueError(f"Invalid case data in row {row_num} of {file_path}: {e}")

        return cases

    def _create_evaluators(self) -> List["Evaluator"]:
        """
        Convert Tactus evaluator configs to Pydantic Evals evaluators.

        Returns:
            List of Pydantic Evals Evaluator instances
        """
        from .evaluators import create_evaluator

        evaluators = []
        for config in self.eval_config.evaluators:
            try:
                evaluator = create_evaluator(config)
                evaluators.append(evaluator)
            except Exception as e:
                logger.warning(f"Failed to create evaluator {config.type}: {e}")

        return evaluators

    def _create_task_function(self) -> Callable:
        """
        Create task function that Pydantic Evals can call.

        The task function:
        - Takes inputs (Dict) as parameter
        - Runs Tactus procedure with those inputs
        - Returns procedure output

        Returns:
            Task function for Pydantic Evals
        """

        def tactus_task(inputs: Dict[str, Any]) -> Dict[str, Any]:
            """
            Execute Tactus procedure with given inputs.

            Args:
                inputs: Procedure parameters (from EvalCase.inputs)

            Returns:
                Procedure output (result dict) with execution trace in metadata
            """
            from tactus.core.runtime import TactusRuntime
            from tactus.adapters.memory import MemoryStorage
            from tactus.testing.mock_hitl import MockHITLHandler
            import time

            # Setup runtime
            storage = MemoryStorage()
            hitl = MockHITLHandler()  # Auto-approve for evals

            runtime = TactusRuntime(
                procedure_id=f"eval_{self.procedure_file.stem}",
                storage_backend=storage,
                hitl_handler=hitl,
                openai_api_key=self.openai_api_key,
            )

            # Execute procedure with inputs as context
            start_time = time.time()
            try:
                result = asyncio.run(
                    runtime.execute(source=self._procedure_source, context=inputs, format="lua")
                )
                duration = time.time() - start_time

                # Extract execution trace from runtime
                trace = self._extract_trace(runtime, duration)

                # Get procedure output
                output = result
                if isinstance(result, dict) and "result" in result:
                    output = result["result"]

                # Return output with trace in special field
                # Pydantic Evals will pass this through to evaluators
                return {"__output__": output, "__trace__": trace}

            except Exception as e:
                logger.error(f"Procedure execution failed: {e}")
                duration = time.time() - start_time
                # Return error info with trace for evaluation
                return {
                    "__output__": {"error": str(e), "success": False},
                    "__trace__": {"duration": duration, "error": str(e)},
                }

        return tactus_task

    def _extract_trace(self, runtime: "TactusRuntime", duration: float) -> Dict[str, Any]:
        """
        Extract execution trace from runtime for evaluators.

        Args:
            runtime: TactusRuntime instance after execution
            duration: Execution duration in seconds

        Returns:
            Dictionary with execution trace information
        """
        trace = {
            "duration": duration,
            "tool_calls": [],
            "state_changes": [],
            "agent_turns": [],
            "iterations": 0,
            "cost": 0.0,
            "tokens": 0,
        }

        # Extract from session if available
        if hasattr(runtime, "session") and runtime.session:
            session = runtime.session

            # Extract tool calls
            if hasattr(session, "tool_calls"):
                trace["tool_calls"] = [
                    {
                        "name": getattr(call, "tool_name", getattr(call, "name", "unknown")),
                        "args": getattr(call, "args", {}),
                        "result": getattr(call, "result", None),
                    }
                    for call in session.tool_calls
                ]

            # Extract agent turns/messages
            if hasattr(session, "messages"):
                for msg in session.messages:
                    if hasattr(msg, "role") and msg.role == "assistant":
                        trace["agent_turns"].append(
                            {
                                "agent": getattr(msg, "agent_name", "unknown"),
                                "message": getattr(msg, "content", ""),
                            }
                        )

            # Extract state changes if tracked
            if hasattr(session, "state_history"):
                trace["state_changes"] = session.state_history

            # Extract metrics
            if hasattr(session, "iteration_count"):
                trace["iterations"] = session.iteration_count

        # Extract cost/token metrics if available
        if hasattr(runtime, "total_cost"):
            trace["cost"] = runtime.total_cost
        if hasattr(runtime, "total_tokens"):
            trace["tokens"] = runtime.total_tokens

        return trace

    def check_thresholds(self, report) -> tuple[bool, list[str]]:
        """
        Check if evaluation results meet configured thresholds.

        Args:
            report: Pydantic Evals EvaluationReport

        Returns:
            Tuple of (passed, violations):
            - passed: True if all thresholds met, False otherwise
            - violations: List of violation messages
        """
        if not self.eval_config.thresholds:
            return True, []

        violations = []
        thresholds = self.eval_config.thresholds

        # Calculate metrics from report
        total_cases = len(report.cases)
        if total_cases == 0:
            return True, []

        # Calculate success rate (all assertions passed)
        passed_cases = sum(
            1
            for case in report.cases
            if hasattr(case, "assertions")
            and case.assertions
            and all(getattr(a, "value", False) for a in case.assertions.values())
        )
        success_rate = passed_cases / total_cases

        # Check success rate threshold
        if thresholds.min_success_rate is not None:
            if success_rate < thresholds.min_success_rate:
                violations.append(
                    f"Success rate {success_rate:.1%} below threshold {thresholds.min_success_rate:.1%}"
                )

        # Calculate average cost per run
        if thresholds.max_cost_per_run is not None:
            total_cost = 0.0
            for case in report.cases:
                if hasattr(case, "cost"):
                    total_cost += getattr(case, "cost", 0.0)
            avg_cost = total_cost / total_cases if total_cases > 0 else 0.0

            if avg_cost > thresholds.max_cost_per_run:
                violations.append(
                    f"Average cost per run ${avg_cost:.4f} exceeds threshold ${thresholds.max_cost_per_run:.4f}"
                )

        # Calculate average duration
        if thresholds.max_duration is not None:
            total_duration = 0.0
            for case in report.cases:
                if hasattr(case, "task_duration"):
                    total_duration += getattr(case, "task_duration", 0.0)
            avg_duration = total_duration / total_cases if total_cases > 0 else 0.0

            if avg_duration > thresholds.max_duration:
                violations.append(
                    f"Average duration {avg_duration:.2f}s exceeds threshold {thresholds.max_duration:.2f}s"
                )

        # Calculate average tokens per run
        if thresholds.max_tokens_per_run is not None:
            total_tokens = 0
            for case in report.cases:
                if hasattr(case, "tokens"):
                    total_tokens += getattr(case, "tokens", 0)
            avg_tokens = total_tokens // total_cases if total_cases > 0 else 0

            if avg_tokens > thresholds.max_tokens_per_run:
                violations.append(
                    f"Average tokens per run {avg_tokens} exceeds threshold {thresholds.max_tokens_per_run}"
                )

        return len(violations) == 0, violations
