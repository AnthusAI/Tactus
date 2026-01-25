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


# ---------------------------------------------------------------------------
# Chat assistant helpers
# ---------------------------------------------------------------------------


class ChatAssistantHarness:
    """
    Test harness for chat assistant that captures tool calls and responses.

    Mocks the LLM to return deterministic tool calls based on message patterns,
    but calls the actual tool implementations to verify they work correctly.
    """

    def __init__(self, workspace_root: str):
        import os

        # Convert to absolute path if relative
        if not os.path.isabs(workspace_root):
            # Resolve relative to project root (where behave is run from)
            workspace_root = os.path.abspath(workspace_root)
        self.workspace_root = workspace_root
        self.config = {}
        self.messages = []
        self.tool_calls = []
        self.response = None

    def configure(self, config: Dict[str, Any]):
        """Configure assistant (provider, model, etc.)"""
        self.config = config

    def send_message(self, message: str):
        """
        Send message and simulate assistant behavior.

        For testing, we mock the LLM's decision-making but call real tools.
        """
        self.messages.append({"role": "user", "content": message})

        # Mock LLM behavior based on message patterns
        message_lower = message.lower()

        if "hello" in message_lower and "show" not in message_lower:
            # Simple greeting - no tools
            self.response = "Hello! How can I help you today?"

        elif "show me" in message_lower or "what files" in message_lower:
            # File operation - simulate tool call
            self._simulate_file_tool_call(message)

        else:
            # Default response
            self.response = "I'm not sure how to help with that."

    def _simulate_file_tool_call(self, message: str):
        """
        Simulate LLM deciding to call the file tool.

        Parse the message to extract file path and determine command,
        then call the actual tool implementation.
        """
        # Extract file path from message
        # Simple pattern matching for testing
        import re

        # Check for line range first (more specific pattern)
        view_range = None
        range_match = re.search(r"lines (\d+)-(\d+) of (.+)", message.lower())
        if range_match:
            start = int(range_match.group(1))
            end = int(range_match.group(2))
            view_range = [start, end]
            path = range_match.group(3).strip()
        else:
            # Pattern: "show me <path>" or "what files in <path>"
            path_match = re.search(r"show me ([^\s]+)", message.lower())
            if not path_match:
                # Pattern: "what files are in this directory"
                if "in this directory" in message.lower():
                    path = "."
                else:
                    # Pattern: "what files are in the <path> directory"
                    path_match = re.search(r"in the ([^\s]+) directory", message.lower())
                    if path_match:
                        # Add trailing slash for directory
                        path = path_match.group(1) + "/"
                    else:
                        self.response = "I couldn't find a file path in your message."
                        return
            else:
                path = path_match.group(1)

        # Determine if it's a directory or file
        command = "view"

        # Call the actual tool (will be implemented later)
        try:
            # For now, just record the call - tool implementation comes next
            tool_result = self._call_tool(command, path, view_range)

            self.tool_calls.append(
                {
                    "tool": "str_replace_based_edit_tool",
                    "params": {
                        "command": command,
                        "path": path,
                        **({"view_range": view_range} if view_range else {}),
                    },
                    "result": tool_result,
                }
            )

            # Generate response based on tool result
            if "Error" in tool_result:
                self.response = f"I encountered an error: {tool_result}"
            else:
                self.response = f"Here's what I found:\n\n{tool_result}"

        except Exception as e:
            self.response = f"Error calling tool: {str(e)}"

    def _call_tool(self, command: str, path: str, view_range: Optional[List[int]] = None) -> str:
        """
        Call the actual tool implementation.
        """
        # Import the real tool
        import sys
        import os

        backend_path = os.path.join(
            os.path.dirname(__file__), "..", "..", "..", "tactus-ide", "backend"
        )
        if backend_path not in sys.path:
            sys.path.insert(0, backend_path)

        from text_editor_tool import str_replace_based_edit_tool

        # Call the real tool
        return str_replace_based_edit_tool(
            workspace_root=self.workspace_root, command=command, path=path, view_range=view_range
        )

    def has_response(self) -> bool:
        """Check if assistant generated a response."""
        return self.response is not None

    def get_response(self) -> str:
        """Get the assistant's response."""
        return self.response or ""

    def get_tool_calls(self) -> List[Dict[str, Any]]:
        """Get list of tool calls made."""
        return self.tool_calls

    def tool_was_called(self, tool_name: str) -> bool:
        """Check if a specific tool was called."""
        return any(call["tool"] == tool_name for call in self.tool_calls)
