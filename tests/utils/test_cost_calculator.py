import pytest

from tactus.utils.cost_calculator import CostCalculator


def test_cost_calculator_basic_costs():
    calculator = CostCalculator()
    result = calculator.calculate_cost(
        model_name="gpt-4o",
        provider="openai",
        prompt_tokens=1000,
        completion_tokens=2000,
    )

    assert result["model"] == "gpt-4o"
    assert result["provider"] == "openai"
    assert result["pricing_found"] is True
    assert result["prompt_cost"] == pytest.approx(0.0025)
    assert result["completion_cost"] == pytest.approx(0.02)
    assert result["total_cost"] == pytest.approx(0.0225)
    assert result["cache_cost"] is None


def test_cost_calculator_with_cache_tokens():
    calculator = CostCalculator()
    result = calculator.calculate_cost(
        model_name="gpt-4o",
        provider="openai",
        prompt_tokens=1000,
        completion_tokens=0,
        cache_tokens=500,
    )

    assert result["cache_cost"] == pytest.approx(0.001125)
    assert result["total_cost"] == pytest.approx(0.0025)
