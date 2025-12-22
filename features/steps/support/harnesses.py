"""
Reusable helpers and lightweight harnesses that back the Behave tests.
"""

from __future__ import annotations

import ast
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterable, List, Optional
from uuid import uuid4

import yaml


# ---------------------------------------------------------------------------
# Generic parsing helpers
# ---------------------------------------------------------------------------


def parse_literal(text: str) -> Any:
    """Parse a Python-style literal used in feature files."""
    try:
        return ast.literal_eval(text)
    except Exception as exc:  # pragma: no cover - diagnostic aid
        raise AssertionError(f"Unable to parse literal '{text}': {exc}") from exc


def table_to_dict(
    table, key_field: str = "parameter", value_field: str = "value"
) -> Dict[str, str]:
    """Convert a Behave table into a dictionary."""
    if table is None:
        return {}
    return {row[key_field]: row[value_field] for row in table}


def parse_key_value_table(table) -> Dict[str, str]:
    """Parse a table with 'key' and 'value' columns."""
    if table is None:
        return {}
    headings = list(table.headings)
    key_column = "key" if "key" in headings else headings[0]
    value_column = "value" if "value" in headings else headings[1]
    return {row[key_column]: row[value_column] for row in table}


def ensure_state_dict(state) -> Dict[str, Any]:
    """Safely expose the underlying state dictionary for primitives."""
    return getattr(state, "_state", {})


@dataclass
class TableData:
    """Simple container for storing parsed table rows."""

    rows: List[Dict[str, Any]] = field(default_factory=list)

    @classmethod
    def from_table(cls, table) -> "TableData":
        return cls([dict(row) for row in (table or [])])


# ---------------------------------------------------------------------------
# Expression evaluation helpers
# ---------------------------------------------------------------------------


class SafeExpressionEvaluator:
    """Evaluate boolean/arithmetic expressions in a safe subset of Python."""

    def __init__(self):
        self.functions = {"len": len, "min": min, "max": max}

    def evaluate(self, expression: str, variables: Dict[str, Any]) -> Any:
        normalized = expression.replace("AND", "and").replace("OR", "or").replace("NOT", "not")
        tree = ast.parse(normalized, mode="eval")
        return self._eval(tree.body, variables)

    def _eval(self, node: ast.AST, variables: Dict[str, Any]) -> Any:
        if isinstance(node, ast.Constant):
            return node.value
        if isinstance(node, ast.Name):
            return variables.get(node.id)
        if isinstance(node, ast.BinOp):
            left = self._eval(node.left, variables)
            right = self._eval(node.right, variables)
            return self._apply_binop(node.op, left, right)
        if isinstance(node, ast.UnaryOp):
            operand = self._eval(node.operand, variables)
            if isinstance(node.op, ast.USub):
                return -operand
            if isinstance(node.op, ast.UAdd):
                return +operand
            if isinstance(node.op, ast.Not):
                return not operand
        if isinstance(node, ast.BoolOp):
            values = [self._eval(value, variables) for value in node.values]
            if isinstance(node.op, ast.And):
                return all(values)
            if isinstance(node.op, ast.Or):
                return any(values)
        if isinstance(node, ast.Compare):
            left = self._eval(node.left, variables)
            for operator, comparator in zip(node.ops, node.comparators):
                right = self._eval(comparator, variables)
                if not self._apply_comparison(operator, left, right):
                    return False
                left = right
            return True
        if isinstance(node, ast.Call):
            func_name = getattr(node.func, "id", None)
            if func_name not in self.functions:
                raise ValueError(f"Function '{func_name}' is not allowed")
            args = [self._eval(arg, variables) for arg in node.args]
            return self.functions[func_name](*args)
        raise ValueError(f"Unsupported expression: {ast.dump(node)}")

    def _apply_binop(self, op: ast.AST, left: Any, right: Any) -> Any:
        if isinstance(op, ast.Add):
            return left + right
        if isinstance(op, ast.Sub):
            return left - right
        if isinstance(op, ast.Mult):
            return left * right
        if isinstance(op, ast.Div):
            return left / right
        if isinstance(op, ast.Mod):
            return left % right
        raise ValueError(f"Unsupported operator: {op}")

    def _apply_comparison(self, operator: ast.AST, left: Any, right: Any) -> bool:
        if isinstance(operator, ast.Gt):
            return left > right
        if isinstance(operator, ast.GtE):
            return left >= right
        if isinstance(operator, ast.Lt):
            return left < right
        if isinstance(operator, ast.LtE):
            return left <= right
        if isinstance(operator, ast.Eq):
            return left == right
        if isinstance(operator, ast.NotEq):
            return left != right
        raise ValueError(f"Unsupported comparison: {operator}")


# ---------------------------------------------------------------------------
# Tool integration helpers
# ---------------------------------------------------------------------------


class FakeToolServer:
    """Deterministic tool registry used by tool-integration steps."""

    def __init__(self):
        self.registry: Dict[str, Callable[[Dict[str, Any]], Any]] = {}
        self.calls: List[Dict[str, Any]] = []
        self.default_parallel_delay = 0.1
        self.register_default_tools()

    def register_default_tools(self):
        self.registry["get_weather"] = lambda params: {
            "location": params.get("location", "Unknown"),
            "temperature": 68,
            "conditions": "Sunny",
        }
        self.registry["get_news"] = lambda params: {
            "category": params.get("category", "general"),
            "headlines": ["AI breakthroughs", "Market update"],
        }
        self.registry["get_stocks"] = lambda params: {
            "symbol": params.get("symbol", "AAPL"),
            "price": 187.42,
        }
        self.registry["long_running_task"] = self._long_running_task
        self.registry["get_paper_details"] = lambda params: {
            "paper_id": params["paper_id"],
            "title": f"Insights for {params['paper_id']}",
        }
        self.registry["search_papers"] = lambda params: [
            "paper-001",
            "paper-002",
            "paper-003",
        ]

    def _long_running_task(self, params: Dict[str, Any]):
        duration = params.get("duration", 10)
        timeout = params.get("timeout")
        if timeout is not None and duration > timeout:
            raise TimeoutError(f"Tool exceeded timeout ({duration}s > {timeout}s)")
        return {"status": "completed", "duration": duration}

    def register(self, name: str, func: Callable[[Dict[str, Any]], Any]):
        self.registry[name] = func

    def call(self, name: str, params: Optional[Dict[str, Any]] = None) -> Any:
        if name not in self.registry:
            raise KeyError(f"Tool '{name}' is not available")
        params = params or {}
        result = self.registry[name](params)
        self.calls.append({"name": name, "params": params, "result": result})
        return result

    def call_parallel(self, calls: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
        responses = []
        start = time.perf_counter()
        for call in calls:
            responses.append(
                {
                    "name": call["tool"],
                    "result": self.call(call["tool"], call.get("params", {})),
                }
            )
        elapsed = time.perf_counter() - start
        return [{"responses": responses, "elapsed": elapsed}]


# ---------------------------------------------------------------------------
# Retry helpers
# ---------------------------------------------------------------------------


class OperationBehavior:
    """
    Deterministic operation used for retry tests.

    Accepts a list describing the outcome for each attempt where each entry
    is either a value (success) or an Exception instance (failure).
    """

    def __init__(self, outcomes: List[Any]):
        self.outcomes = outcomes
        self.attempts = 0

    def __call__(self):
        index = min(self.attempts, len(self.outcomes) - 1)
        outcome = self.outcomes[index]
        self.attempts += 1
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


# ---------------------------------------------------------------------------
# Logging helpers
# ---------------------------------------------------------------------------


class InMemoryLogHandler(logging.Handler):
    """Captures log records for assertions."""

    def __init__(self):
        super().__init__()
        self.records: List[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)

    def clear(self):
        self.records.clear()


# ---------------------------------------------------------------------------
# Stage tracking helpers
# ---------------------------------------------------------------------------


@dataclass
class StageInfo:
    stage_id: str
    name: str
    status: str = "pending"
    steps: Dict[str, str] = field(default_factory=dict)
    children: List[str] = field(default_factory=list)
    progress: float = 0.0
    failure_reason: Optional[str] = None


class StageTracker:
    """Lightweight stage/step tracker mirroring the feature requirements."""

    def __init__(self):
        self.stages: Dict[str, StageInfo] = {}
        self.current_stage: Optional[str] = None
        self.history: List[str] = []
        self.progress_updates: List[str] = []
        self.clock_seconds: float = 0.0
        self.step_timings: Dict[str, Dict[str, float]] = {}

    def define_stages(self, table):
        self.stages.clear()
        for row in table:
            self.stages[row["stage_id"]] = StageInfo(
                stage_id=row["stage_id"],
                name=row["name"],
            )

    def define_numeric_stages(self, count: int):
        self.stages.clear()
        for idx in range(1, count + 1):
            stage_id = f"stage{idx}"
            self.stages[stage_id] = StageInfo(stage_id=stage_id, name=f"Stage {idx}")

    def begin_stage(self, stage_id: str):
        stage = self._get(stage_id)
        stage.status = "in_progress"
        self.current_stage = stage_id
        self.history.append(stage_id)
        self.progress_updates.append(f"Stage {stage.name} started")

    def complete_stage(self, stage_id: str):
        stage = self._get(stage_id)
        stage.status = "completed"
        self.progress_updates.append(f"Stage {stage.name} completed")

    def mark_failed(self, stage_id: str, reason: str):
        stage = self._get(stage_id)
        stage.status = "failed"
        stage.failure_reason = reason

    def track_step(self, stage_id: str, step_name: str, status: str):
        stage = self._get(stage_id)
        stage.steps[step_name] = status

    def set_children(self, parent: str, child_stage_ids: List[str]):
        parent_stage = self._get(parent)
        parent_stage.children = child_stage_ids

    def set_child_completion(self, parent: str):
        parent_stage = self._get(parent)
        completed = sum(
            1 for child in parent_stage.children if self._get(child).status == "completed"
        )
        total = max(len(parent_stage.children), 1)
        parent_stage.progress = completed / total * 100

    def set_progress(self, stage_id: str, completed_steps: int, total_steps: int):
        stage = self._get(stage_id)
        if total_steps == 0:
            stage.progress = 0
        else:
            stage.progress = completed_steps / total_steps * 100

    def advance_time(self, seconds: float):
        self.clock_seconds += seconds

    def begin_step_timing(self, stage_id: str, step_name: str):
        self.step_timings.setdefault(stage_id, {})[step_name] = self.clock_seconds
        self.track_step(stage_id, step_name, "in_progress")

    def complete_step_timing(self, stage_id: str, step_name: str):
        start = self.step_timings.get(stage_id, {}).get(step_name, self.clock_seconds)
        duration = self.clock_seconds - start
        self.track_step(stage_id, step_name, "completed")
        return duration

    def _get(self, stage_id: str) -> StageInfo:
        if stage_id not in self.stages:
            raise KeyError(f"Stage '{stage_id}' is not defined")
        return self.stages[stage_id]


# ---------------------------------------------------------------------------
# Procedure runtime helpers
# ---------------------------------------------------------------------------


@dataclass
class ProcedureDefinition:
    name: str
    handler: Callable[[Dict[str, Any], Dict[str, Any], "ProcedureRuntime"], Any]
    duration: float = 0.0
    checkpoint: bool = False


class ProcedureRuntime:
    """Tiny interpreter capable of running declarative procedure snippets."""

    def __init__(self):
        self.registry: Dict[str, ProcedureDefinition] = {}
        self.call_stack: List[str] = []
        self.checkpoints: Dict[str, Any] = {}

    def register_callable(
        self,
        name: str,
        handler: Callable[[Dict[str, Any], Dict[str, Any], "ProcedureRuntime"], Any],
        duration: float = 0.0,
        checkpoint: bool = False,
    ):
        self.registry[name] = ProcedureDefinition(name, handler, duration, checkpoint)

    def register_yaml(self, yaml_text: str):
        data = yaml.safe_load(yaml_text)

        def handler(params: Dict[str, Any], state: Dict[str, Any], runtime: "ProcedureRuntime"):
            steps = data.get("steps", [])
            for step in steps:
                action = step.get("action")
                if action == "state.set":
                    key = step["params"]["key"]
                    value_expr = step["params"]["value"]
                    value = value_expr
                    if isinstance(value_expr, str) and value_expr.startswith("{{"):
                        expr = value_expr.strip("{} ").strip()
                        evaluator = SafeExpressionEvaluator()
                        value = evaluator.evaluate(expr, {**params, **state})
                    state[key] = value
            return state.get("result")

        self.register_callable(data["name"], handler)

    def call(
        self,
        name: str,
        params: Optional[Dict[str, Any]] = None,
        state: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None,
    ):
        if name not in self.registry:
            raise KeyError(f"Procedure '{name}' is not registered")
        params = params or {}
        state = state.copy() if state else {}
        definition = self.registry[name]
        if timeout and definition.duration > timeout:
            raise TimeoutError(f"Procedure '{name}' exceeded timeout")
        self.call_stack.append(name)
        try:
            result = definition.handler(params, state, self)
            if definition.checkpoint:
                self.checkpoints[name] = result
            return result, state
        finally:
            self.call_stack.pop()


# ---------------------------------------------------------------------------
# Session management helpers
# ---------------------------------------------------------------------------


@dataclass
class SessionRecord:
    session_id: str
    context: Dict[str, Any]
    metadata: Dict[str, Any] = field(default_factory=dict)
    messages: List[Dict[str, Any]] = field(default_factory=list)
    status: str = "ACTIVE"
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None

    def duration(self) -> float:
        end = self.end_time or time.time()
        return end - self.start_time


class FakeSessionStore:
    """Simple in-memory session tracker for session-management scenarios."""

    def __init__(self):
        self.sessions: Dict[str, SessionRecord] = {}

    def start_session(
        self, context: Dict[str, Any], metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        session_id = str(uuid4())
        self.sessions[session_id] = SessionRecord(
            session_id=session_id,
            context=context,
            metadata=metadata or {},
        )
        return session_id

    def record_message(
        self,
        session_id: str,
        role: str,
        content: str,
        message_type: str = "agent",
        extra: Optional[Dict[str, Any]] = None,
    ):
        session = self.sessions[session_id]
        session.messages.append(
            {
                "role": role,
                "content": content,
                "type": message_type,
                "timestamp": time.time(),
                "extra": extra or {},
            }
        )

    def end_session(self, session_id: str, status: str):
        session = self.sessions[session_id]
        session.status = status.upper()
        session.end_time = time.time()

    def export(self, session_id: str) -> str:
        session = self.sessions[session_id]
        payload = {
            "session_id": session.session_id,
            "context": session.context,
            "metadata": session.metadata,
            "messages": session.messages,
            "status": session.status,
        }
        return json.dumps(payload, indent=2)

    def query_by_task_type(self, task_type: str) -> List[SessionRecord]:
        return [
            session
            for session in self.sessions.values()
            if session.context.get("task_type") == task_type
        ]
