"""
Pydantic models for Pydantic Evals integration.

These models define the structure of evaluation configurations
that can be declared in .tac files using the evaluations() function.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class EvalCase(BaseModel):
    """
    Single evaluation test case.

    Represents one test case in an evaluation dataset with inputs,
    optional expected outputs, and metadata.
    """

    name: str
    inputs: Dict[str, Any]  # Procedure parameters
    expected_output: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class EvaluatorConfig(BaseModel):
    """
    Configuration for an evaluator.

    Defines how to evaluate procedure outputs. Different evaluator types
    have different configuration requirements.
    """

    type: str  # "contains", "llm_judge", "exact_match", "min_length", etc.

    # Common fields (used by different evaluator types)
    field: Optional[str] = None  # Which output field to evaluate
    value: Optional[Any] = None  # Value to check against
    check_expected: Optional[str] = None  # Field name in expected_output to check

    # LLM-as-judge specific
    rubric: Optional[str] = None  # Evaluation rubric for LLM judge
    model: Optional[str] = None  # Model to use for LLM judge
    include_expected: bool = False  # Whether to include expected_output in prompt

    # Tactus-specific evaluators
    max_iterations: Optional[int] = None
    max_cost: Optional[float] = None
    max_tokens: Optional[int] = None

    # Regex evaluator
    pattern: Optional[str] = None
    case_sensitive: bool = True

    # JSON Schema evaluator
    json_schema: Optional[Dict[str, Any]] = None

    # Numeric range evaluator
    min_value: Optional[float] = None
    max_value: Optional[float] = None


class EvaluationThresholds(BaseModel):
    """
    Quality gates for CI/CD integration.

    Defines minimum acceptable thresholds for evaluation metrics.
    If any threshold is not met, the evaluation fails.
    """

    min_success_rate: Optional[float] = None  # 0.0-1.0 (e.g., 0.90 for 90%)
    max_cost_per_run: Optional[float] = None  # Maximum cost in dollars
    max_duration: Optional[float] = None  # Maximum duration in seconds
    max_tokens_per_run: Optional[int] = None  # Maximum tokens per run


class EvaluationConfig(BaseModel):
    """
    Complete evaluation configuration from evaluations() call.

    Contains the dataset, evaluators, and execution settings for
    running Pydantic Evals on a Tactus procedure.
    """

    dataset: List[EvalCase]
    evaluators: List[EvaluatorConfig]
    runs: int = 1  # Number of times to run each case
    parallel: bool = True  # Whether to run cases in parallel
    dataset_file: Optional[str] = None  # Path to external dataset file
    thresholds: Optional[EvaluationThresholds] = None  # Quality gates for CI/CD


class EvaluationResultSummary(BaseModel):
    """
    Summary of evaluation results.

    Aggregates results across all cases and runs for reporting.
    """

    total_cases: int
    passed_cases: int
    failed_cases: int

    # Aggregate metrics
    mean_score: Optional[float] = None  # Average score from LLM judges
    consistency_score: Optional[float] = None  # Consistency across runs

    # Performance metrics
    total_cost: float = 0.0
    total_tokens: int = 0
    total_duration: float = 0.0

    # Per-case results
    case_results: List[Dict[str, Any]] = Field(default_factory=list)
