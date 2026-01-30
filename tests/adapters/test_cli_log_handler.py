from tactus.adapters.cli_log import CLILogHandler
from tactus.protocols.models import (
    LogEvent,
    CostEvent,
    AgentTurnEvent,
    ToolCallEvent,
    AgentStreamChunkEvent,
    ExecutionSummaryEvent,
    CheckpointCreatedEvent,
    SourceLocation,
)


class DummyConsole:
    def __init__(self):
        self.messages = []

    def print(self, *args, **kwargs):
        self.messages.append(" ".join(str(a) for a in args))

    def log(self, message):
        self.messages.append(message)


def test_log_handler_records_cost_event():
    console = DummyConsole()
    handler = CLILogHandler(console=console)
    event = CostEvent(
        agent_name="agent",
        model="m",
        provider="openai",
        prompt_tokens=1,
        completion_tokens=2,
        total_tokens=3,
        prompt_cost=0.1,
        completion_cost=0.2,
        total_cost=0.3,
    )
    handler.log(event)
    assert handler.cost_events


def test_log_handler_handles_agent_events():
    console = DummyConsole()
    handler = CLILogHandler(console=console)
    handler.log(AgentTurnEvent(agent_name="a", stage="started"))
    handler.log(AgentTurnEvent(agent_name="a", stage="completed", duration_ms=10))
    assert console.messages


def test_log_handler_ignores_unknown_agent_stage():
    console = DummyConsole()
    handler = CLILogHandler(console=console)
    handler.log(AgentTurnEvent(agent_name="a", stage="unknown"))
    assert console.messages == []


def test_log_handler_handles_tool_call_and_checkpoint():
    console = DummyConsole()
    handler = CLILogHandler(console=console)
    handler.log(ToolCallEvent(agent_name="a", tool_name="t", tool_args={"x": 1}, tool_result="ok"))
    handler.log(
        CheckpointCreatedEvent(
            checkpoint_position=1,
            checkpoint_type="agent_turn",
            duration_ms=5,
            source_location=SourceLocation(file="x.tac", line=1),
        )
    )
    assert console.messages


def test_log_handler_handles_stream_and_summary():
    console = DummyConsole()
    handler = CLILogHandler(console=console)
    handler.log(AgentStreamChunkEvent(agent_name="a", chunk_text="hi", accumulated_text="hi"))
    handler.log(
        ExecutionSummaryEvent(
            result={"ok": True},
            iterations=1,
            tools_used=["done"],
            total_cost=0.1,
            total_tokens=10,
        )
    )
    assert console.messages


def test_log_handler_fallback_log_event():
    console = DummyConsole()
    handler = CLILogHandler(console=console)
    handler.log(LogEvent(level="INFO", message="hello", context={"a": 1}))
    assert any("hello" in msg for msg in console.messages)


def test_log_handler_fallback_without_context():
    console = DummyConsole()
    handler = CLILogHandler(console=console)
    handler.log(LogEvent(level="INFO", message="plain"))
    assert any("plain" in msg for msg in console.messages)


def test_log_handler_tool_call_complex_args_and_long_result():
    console = DummyConsole()
    handler = CLILogHandler(console=console)
    long_result = "x" * 100
    handler.log(
        ToolCallEvent(
            agent_name="a",
            tool_name="t",
            tool_args={"x": 1, "y": 2},
            tool_result=long_result,
        )
    )
    assert any("Args:" in msg for msg in console.messages)
    assert any("Result:" in msg for msg in console.messages)


def test_log_handler_tool_call_without_args_or_result():
    console = DummyConsole()
    handler = CLILogHandler(console=console)
    handler.log(ToolCallEvent(agent_name="a", tool_name="t", tool_args={}, tool_result=None))
    assert console.messages


def test_log_handler_checkpoint_without_location():
    console = DummyConsole()
    handler = CLILogHandler(console=console)
    handler.log(
        CheckpointCreatedEvent(
            checkpoint_position=1,
            checkpoint_type="agent_turn",
            duration_ms=None,
            source_location=None,
        )
    )
    assert console.messages


def test_log_handler_cost_event_with_retry_and_cache():
    console = DummyConsole()
    handler = CLILogHandler(console=console)
    event = CostEvent(
        agent_name="agent",
        model="m",
        provider="openai",
        prompt_tokens=1,
        completion_tokens=2,
        total_tokens=3,
        prompt_cost=0.1,
        completion_cost=0.2,
        total_cost=0.3,
        retry_count=1,
        cache_hit=True,
        cache_tokens=10,
        cache_cost=0.05,
    )
    handler.log(event)
    assert any("Retried" in msg for msg in console.messages)
    assert any("Cache hit" in msg for msg in console.messages)


def test_log_handler_execution_summary_with_breakdowns_and_checkpoints():
    console = DummyConsole()
    handler = CLILogHandler(console=console)
    cost = CostEvent(
        agent_name="agent",
        model="m",
        provider="openai",
        prompt_tokens=1,
        completion_tokens=2,
        total_tokens=3,
        prompt_cost=0.1,
        completion_cost=0.2,
        total_cost=0.3,
        duration_ms=5,
    )
    handler.log(
        ExecutionSummaryEvent(
            result={"ok": True},
            iterations=1,
            tools_used=["done"],
            total_cost=0.1,
            total_tokens=10,
            cost_breakdown=[cost],
            checkpoint_count=2,
            checkpoint_types={"agent_turn": 2},
            checkpoint_duration_ms=100,
        )
    )
    assert any("Cost Summary" in msg for msg in console.messages)
    assert any("Checkpoint Summary" in msg for msg in console.messages)


def test_log_handler_execution_summary_without_costs_or_checkpoints():
    console = DummyConsole()
    handler = CLILogHandler(console=console)
    handler.log(
        ExecutionSummaryEvent(
            result={"ok": True},
            iterations=1,
            tools_used=[],
            total_cost=0.0,
            total_tokens=0,
            checkpoint_count=0,
        )
    )
    assert any("Procedure completed" in msg for msg in console.messages)


def test_log_handler_execution_summary_checkpoint_without_types_or_duration():
    console = DummyConsole()
    handler = CLILogHandler(console=console)
    handler.log(
        ExecutionSummaryEvent(
            result={"ok": True},
            iterations=1,
            tools_used=[],
            total_cost=0.0,
            total_tokens=0,
            checkpoint_count=1,
            checkpoint_types={},
            checkpoint_duration_ms=None,
        )
    )
    assert any("Checkpoint Summary" in msg for msg in console.messages)
