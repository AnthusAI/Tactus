import pytest

from tactus.adapters.file_storage import FileStorage
from tactus.adapters.memory import MemoryStorage
from tactus.core.exceptions import RunSpendBudgetExceeded
from tactus.core.execution_context import BaseExecutionContext
from tactus.core.mocking import MockManager
from tactus.core.run_spend_budget import (
    RunSpendBudget,
    extract_spend_from_checkpoint_result,
    summarize_run_spend,
)
from tactus.core.runtime import TactusRuntime
from tactus.dspy.agent import DSPyAgentHandle
from tactus.protocols.cost import CostStats, UsageStats
from tactus.protocols.result import TactusResult


def build_agent_turn_result(cost_usd: float, total_tokens: int) -> TactusResult:
    return TactusResult(
        output="turn output",
        usage=UsageStats(total_tokens=total_tokens),
        cost_stats=CostStats(total_cost=cost_usd),
    )


def test_extract_spend_reads_result_objects_and_serialized_dictionaries():
    spend_from_object = extract_spend_from_checkpoint_result(build_agent_turn_result(0.25, 120))
    spend_from_dictionary = extract_spend_from_checkpoint_result(
        {"output": "x", "usage": {"total_tokens": 120}, "cost_stats": {"total_cost": 0.25}}
    )
    spend_from_plain_value = extract_spend_from_checkpoint_result("plain checkpoint value")

    assert spend_from_object.cost_usd == pytest.approx(0.25)
    assert spend_from_object.total_tokens == 120
    assert spend_from_dictionary == spend_from_object
    assert spend_from_plain_value.cost_usd == 0.0
    assert spend_from_plain_value.total_tokens == 0


def test_agent_turn_is_refused_once_cost_budget_is_spent():
    execution_context = BaseExecutionContext("procedure", MemoryStorage())
    execution_context.set_run_id("run-1")
    execution_context.set_run_spend_budget(RunSpendBudget(max_cost_usd=1.0))

    execution_context.checkpoint(lambda: build_agent_turn_result(0.6, 10), "agent_turn")
    execution_context.checkpoint(lambda: build_agent_turn_result(0.6, 10), "agent_worker_turn")

    with pytest.raises(RunSpendBudgetExceeded) as raised:
        execution_context.checkpoint(lambda: build_agent_turn_result(0.6, 10), "agent_turn")

    assert raised.value.exhausted_limit_name == "max_cost_usd"
    assert raised.value.spent_value == pytest.approx(1.2)


def test_non_agent_checkpoints_still_run_after_budget_is_spent():
    execution_context = BaseExecutionContext("procedure", MemoryStorage())
    execution_context.set_run_spend_budget(RunSpendBudget(max_total_tokens=100))
    execution_context.checkpoint(lambda: build_agent_turn_result(0.0, 150), "agent_turn")

    assert execution_context.checkpoint(lambda: "saved", "step") == "saved"


def test_replayed_turns_are_not_counted_twice_and_budget_survives_resume(tmp_path):
    storage = FileStorage(str(tmp_path / "storage"))
    turn_executions = {"count": 0}

    def execute_agent_turn():
        turn_executions["count"] += 1
        return build_agent_turn_result(0.4, 10)

    first_process_context = BaseExecutionContext("procedure", storage)
    first_process_context.set_run_id("run-1")
    first_process_context.set_run_spend_budget(RunSpendBudget(max_cost_usd=1.0))
    first_process_context.checkpoint(execute_agent_turn, "agent_turn")
    first_process_context.checkpoint(execute_agent_turn, "agent_turn")
    storage.save_procedure_metadata("procedure", first_process_context.metadata)

    resumed_process_context = BaseExecutionContext("procedure", storage)
    resumed_process_context.set_run_id("run-1")
    resumed_process_context.set_run_spend_budget(RunSpendBudget(max_cost_usd=1.0))
    resumed_process_context.checkpoint(execute_agent_turn, "agent_turn")
    resumed_process_context.checkpoint(execute_agent_turn, "agent_turn")
    assert turn_executions["count"] == 2
    assert resumed_process_context.current_run_spend().cost_usd == pytest.approx(0.8)

    resumed_process_context.checkpoint(execute_agent_turn, "agent_turn")
    with pytest.raises(RunSpendBudgetExceeded):
        resumed_process_context.checkpoint(execute_agent_turn, "agent_turn")


def test_spend_from_other_runs_is_ignored():
    execution_context = BaseExecutionContext("procedure", MemoryStorage())
    execution_context.set_run_id("run-1")
    execution_context.checkpoint(lambda: build_agent_turn_result(5.0, 10), "agent_turn")

    assert summarize_run_spend(execution_context.metadata.execution_log, "run-2").cost_usd == 0.0


@pytest.mark.asyncio
async def test_procedure_budget_stops_a_mocked_agent_loop(tmp_path, monkeypatch):
    original_wrap_mock_response = DSPyAgentHandle._wrap_mock_response

    def wrap_mock_response_with_token_usage(agent, mock_data, turn_options):
        mocked_result = original_wrap_mock_response(agent, mock_data, turn_options)
        mocked_result.usage = UsageStats(total_tokens=100)
        return mocked_result

    monkeypatch.setattr(
        DSPyAgentHandle, "_wrap_mock_response", wrap_mock_response_with_token_usage
    )
    source = """
Mocks {
    worker = {
        message = "working"
    }
}

worker = Agent {
    provider = "openai",
    model = "gpt-4o-mini",
    system_prompt = "Work"
}

Procedure {
    budget = { max_total_tokens = 150 },
    output = { turns = field.number{required = true} },
    function(input)
        local turns = 0
        for _ = 1, 5 do
            worker()
            turns = turns + 1
        end
        return { turns = turns }
    end
}
"""
    runtime = TactusRuntime(
        procedure_id="budgeted", storage_backend=FileStorage(str(tmp_path / "storage"))
    )
    runtime.mock_manager = MockManager()

    result = await runtime.execute(source, context={}, format="lua")

    assert not result["success"]
    assert "max_total_tokens" in result["error"]


@pytest.mark.asyncio
async def test_budget_on_a_sub_procedure_is_rejected(tmp_path):
    source = """
helper = Procedure "helper" {
    budget = { max_cost_usd = 1 },
    function(input)
        return {}
    end
}

Procedure {
    function(input)
        return {}
    end
}
"""
    runtime = TactusRuntime(
        procedure_id="invalid", storage_backend=FileStorage(str(tmp_path / "storage"))
    )

    result = await runtime.execute(source, context={}, format="lua")

    assert not result["success"]
    assert "only supported on the main procedure" in result["error"]
