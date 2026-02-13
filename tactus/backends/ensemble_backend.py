"""
Ensemble and A/B test backends for Model primitive.
"""

from __future__ import annotations

import random
import time
from typing import Any, List, Sequence

from tactus.models.types import PredictionCost


class MockBackend:
    """Simple backend that returns a fixed value (useful for testing/ensembles)."""

    def __init__(self, value: Any):
        self.value = value

    async def predict(self, input_data: Any) -> Any:
        return self.predict_sync(input_data)

    def predict_sync(self, input_data: Any) -> Any:
        return self.value


class EnsembleBackend:
    """
    Ensemble backend that aggregates predictions from multiple backends.
    Supports simple majority vote (strings) or average (numbers).
    """

    def __init__(self, backends: Sequence[Any], strategy: str = "vote"):
        self.backends = list(backends)
        self.strategy = strategy

    async def predict(self, input_data: Any) -> Any:
        return self.predict_sync(input_data)

    def predict_sync(self, input_data: Any) -> dict:
        start = time.perf_counter()
        outputs = []
        for backend in self.backends:
            result = backend.predict_sync(input_data)
            if isinstance(result, dict) and "result" in result:
                outputs.append(result["result"])
            elif hasattr(result, "output"):
                outputs.append(result.output)
            else:
                outputs.append(result)

        combined = self._combine(outputs)
        elapsed_ms = (time.perf_counter() - start) * 1000
        cost = PredictionCost(compute_time_ms=elapsed_ms)
        return {"result": combined, "cost": {"compute_time_ms": cost.compute_time_ms}, "meta": {"votes": outputs}}

    def _combine(self, outputs: List[Any]) -> Any:
        if self.strategy == "average":
            nums = [o for o in outputs if isinstance(o, (int, float))]
            return sum(nums) / len(nums) if nums else None

        # default: vote
        counts = {}
        for o in outputs:
            counts[o] = counts.get(o, 0) + 1
        return max(counts.items(), key=lambda kv: kv[1])[0] if counts else None


class ABTestBackend:
    """Route traffic between multiple backends according to weights."""

    def __init__(self, backends: Sequence[Any], weights: Sequence[float] | None = None, seed: int | None = None):
        self.backends = list(backends)
        self.weights = list(weights) if weights else [1.0] * len(backends)
        self.random = random.Random(seed)

    async def predict(self, input_data: Any) -> Any:
        return self.predict_sync(input_data)

    def predict_sync(self, input_data: Any) -> Any:
        idx = self._choose_index()
        chosen = self.backends[idx]
        result = chosen.predict_sync(input_data)
        if isinstance(result, dict) and "result" in result:
            result.setdefault("meta", {})
            result["meta"]["arm_index"] = idx
            return result
        return {"result": result, "meta": {"arm_index": idx}}

    def _choose_index(self) -> int:
        total = sum(self.weights)
        r = self.random.random() * total
        upto = 0.0
        for i, w in enumerate(self.weights):
            upto += w
            if upto >= r:
                return i
        return len(self.weights) - 1
