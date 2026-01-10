"""
Cost and usage models shared across Tactus.

These models are intentionally small and stable so they can be reused anywhere
that may incur cost (agents, results, future primitives).
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class UsageStats(BaseModel):
    """Token usage for a single call or an aggregate."""

    prompt_tokens: int = Field(default=0, ge=0)
    completion_tokens: int = Field(default=0, ge=0)
    total_tokens: int = Field(default=0, ge=0)


class CostStats(BaseModel):
    """Cost for a single call or an aggregate."""

    total_cost: float = Field(default=0.0, ge=0.0, description="Total cost in USD")
    prompt_cost: float = Field(default=0.0, ge=0.0)
    completion_cost: float = Field(default=0.0, ge=0.0)

    model: Optional[str] = Field(default=None, description="Model identifier, if known")
    provider: Optional[str] = Field(default=None, description="Provider identifier, if known")
