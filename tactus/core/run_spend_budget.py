"""
Run-level spend budgets for model calls.

A budget caps what one run may spend on model calls, in dollars and in tokens.
Spend is derived from the checkpointed execution log rather than kept in a
separate counter, so a run that suspends for a human and resumes days later is
still held to the same budget, and replayed turns are never counted twice.

The budget is checked before each new agent turn. The turn that crosses a limit
is allowed to finish, because its cost is only known afterwards; the next turn
is refused with RunSpendBudgetExceeded.
"""

from __future__ import annotations

from typing import Any, Iterable, Optional

from pydantic import BaseModel, Field

from tactus.core.exceptions import RunSpendBudgetExceeded


class RunSpendBudget(BaseModel):
    max_cost_usd: Optional[float] = Field(default=None, gt=0)
    max_total_tokens: Optional[int] = Field(default=None, gt=0)

    model_config = {"extra": "forbid"}


class RunSpendTotals(BaseModel):
    cost_usd: float = 0.0
    total_tokens: int = 0


def is_agent_turn_checkpoint_type(checkpoint_type: str) -> bool:
    if checkpoint_type == "agent_turn":
        return True
    return checkpoint_type.startswith("agent_") and checkpoint_type.endswith("_turn")


def is_model_spending_checkpoint_type(checkpoint_type: str) -> bool:
    return is_agent_turn_checkpoint_type(checkpoint_type) or checkpoint_type == "model_predict"


def _read_field(container: Any, field_name: str) -> Any:
    if isinstance(container, dict):
        return container.get(field_name)
    return getattr(container, field_name, None)


def extract_spend_from_checkpoint_result(checkpoint_result: Any) -> RunSpendTotals:
    if checkpoint_result is None:
        return RunSpendTotals()

    cost_stats = _read_field(checkpoint_result, "cost_stats")
    usage_stats = _read_field(checkpoint_result, "usage")
    if cost_stats is None and usage_stats is None:
        return RunSpendTotals()

    return RunSpendTotals(
        cost_usd=float(_read_field(cost_stats, "total_cost") or 0.0) if cost_stats else 0.0,
        total_tokens=int(_read_field(usage_stats, "total_tokens") or 0) if usage_stats else 0,
    )


def summarize_run_spend(execution_log: Iterable[Any], run_id: Optional[str]) -> RunSpendTotals:
    accumulated_cost_usd = 0.0
    accumulated_total_tokens = 0
    for checkpoint_entry in execution_log:
        if checkpoint_entry.run_id != run_id:
            continue
        if not is_model_spending_checkpoint_type(checkpoint_entry.type):
            continue
        checkpoint_spend = extract_spend_from_checkpoint_result(checkpoint_entry.result)
        accumulated_cost_usd += checkpoint_spend.cost_usd
        accumulated_total_tokens += checkpoint_spend.total_tokens
    return RunSpendTotals(cost_usd=accumulated_cost_usd, total_tokens=accumulated_total_tokens)


def raise_if_run_spend_budget_exhausted(
    run_spend_budget: RunSpendBudget, run_spend_totals: RunSpendTotals
) -> None:
    if (
        run_spend_budget.max_cost_usd is not None
        and run_spend_totals.cost_usd >= run_spend_budget.max_cost_usd
    ):
        raise RunSpendBudgetExceeded(
            exhausted_limit_name="max_cost_usd",
            limit_value=run_spend_budget.max_cost_usd,
            spent_value=run_spend_totals.cost_usd,
        )
    if (
        run_spend_budget.max_total_tokens is not None
        and run_spend_totals.total_tokens >= run_spend_budget.max_total_tokens
    ):
        raise RunSpendBudgetExceeded(
            exhausted_limit_name="max_total_tokens",
            limit_value=run_spend_budget.max_total_tokens,
            spent_value=run_spend_totals.total_tokens,
        )
