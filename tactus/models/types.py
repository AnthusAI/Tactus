"""
Data types for Model primitive results and cost tracking.
"""

from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class PredictionCost:
    """Cost of a single prediction.

    Cost tracking is only applicable for some model types:
    - LLM backends: Token-based cost from provider pricing
    - HTTP backends: Per-call cost if configured
    - PyTorch/sklearn/ONNX: No per-prediction cost (compute is local)
    """

    inference_cost: Optional[float] = None  # Dollar cost (LLM tokens, API calls)
    compute_time_ms: Optional[float] = None  # Wall clock time
    tokens_in: Optional[int] = None  # Input tokens (LLM only)
    tokens_out: Optional[int] = None  # Output tokens (LLM only)

    @property
    def total_cost(self) -> Optional[float]:
        """Return the total inference cost."""
        return self.inference_cost


@dataclass
class PredictionResult:
    """Result from a model prediction.

    This wraps the model's output with metadata about the prediction,
    including cost tracking and versioning information.

    Supports dict-like access for backward compatibility and Lua interop:
    - result.output or result["output"] → the prediction
    - result.cost or result["cost"] → cost information
    """

    output: Any  # The actual prediction
    cost: Optional[PredictionCost] = None  # Cost info (if applicable)
    model_version: Optional[str] = None  # Which version was used
    backend_type: Optional[str] = None  # Which backend ran it
    metadata: Optional[dict] = None  # Additional metadata (e.g., chosen arm, votes)

    def __getitem__(self, key: str) -> Any:
        """Enable dict-like access for Lua compatibility."""
        if key == "output":
            return self.output
        elif key == "cost":
            return self.cost
        elif key == "model_version":
            return self.model_version
        elif key == "backend_type":
            return self.backend_type
        elif key == "metadata":
            return self.metadata
        else:
            # For backward compat, try to access nested fields in output
            if isinstance(self.output, dict):
                return self.output.get(key)
            raise KeyError(f"No field '{key}' in PredictionResult")

    def get(self, key: str, default: Any = None) -> Any:
        """Dict-like get with default value."""
        try:
            return self[key]
        except KeyError:
            return default
