"""
Result object returned by cost-incurring primitives (e.g., Agents).

Standardizes on `result.output` for the returned data (string or structured).
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, PrivateAttr

from tactus.protocols.cost import UsageStats, CostStats


class TactusResult(BaseModel):
    """
    Standard Result wrapper for Lua and Python consumption.

    - `output`: The returned data (string or structured dict/list/etc.)
    - `usage`: Token usage stats for the call that produced this result
    - `cost_stats`: Cost stats for the call that produced this result
    """

    output: Any = Field(..., description="Result output (string or structured data)")
    usage: UsageStats = Field(default_factory=UsageStats)
    cost_stats: CostStats = Field(default_factory=CostStats)

    model_config = {"arbitrary_types_allowed": True}

    _prediction: Any | None = PrivateAttr(default=None)
    _new_messages: list[dict[str, Any]] = PrivateAttr(default_factory=list)
    _all_messages: list[dict[str, Any]] = PrivateAttr(default_factory=list)

    def __getattr__(self, item: str) -> Any:
        """
        Proxy unknown attributes to the underlying prediction (when present).

        This keeps a smooth migration path for callers that expect `result.response`,
        `result.tool_calls`, etc., while preserving the stable `result.output` field.
        """
        private_attrs = getattr(type(self), "__private_attributes__", {}) or {}
        if item.startswith("_"):
            if item in private_attrs:
                private = object.__getattribute__(self, "__pydantic_private__")
                if isinstance(private, dict) and item in private:
                    return private[item]
            raise AttributeError(f"{type(self).__name__!r} object has no attribute {item!r}")

        private = object.__getattribute__(self, "__pydantic_private__")
        prediction = private.get("_prediction") if isinstance(private, dict) else None
        if prediction is not None:
            try:
                return getattr(prediction, item)
            except AttributeError:
                pass

        if isinstance(self.output, dict) and item in self.output:
            return self.output[item]

        raise AttributeError(f"{type(self).__name__!r} object has no attribute {item!r}")

    def cost(self) -> CostStats:
        """Return cost statistics for this result."""
        return self.cost_stats

    def new_messages(self) -> list[dict[str, Any]]:
        """Return messages added during the producing agent turn (if available)."""
        return list(self._new_messages)

    def all_messages(self) -> list[dict[str, Any]]:
        """Return the full conversation history (if available)."""
        return list(self._all_messages)

    def _set_messages(
        self,
        *,
        new_messages: list[dict[str, Any]] | None,
        all_messages: list[dict[str, Any]] | None,
    ) -> "TactusResult":
        self._new_messages = list(new_messages or [])
        self._all_messages = list(all_messages or [])
        return self

    def _set_prediction(self, prediction: Any | None) -> "TactusResult":
        self._prediction = prediction
        return self
