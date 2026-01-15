"""
Result object returned by cost-incurring primitives (e.g., Agents).

Standardizes on `result.output` for the returned data (string or structured).
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

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

    def cost(self) -> CostStats:
        """Return cost statistics for this result."""
        return self.cost_stats
