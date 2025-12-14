"""
Evaluator mapping for Pydantic Evals integration.

This module maps Tactus evaluator configurations to Pydantic Evals
evaluator instances, including both built-in and custom evaluators.
"""

import logging
from dataclasses import dataclass
from typing import Optional

from .eval_models import EvaluatorConfig
from typing import Any

logger = logging.getLogger(__name__)

# Check if pydantic_evals is available
try:
    from pydantic_evals.evaluators import (
        Evaluator,
        EvaluatorContext,
        Contains,
        EqualsExpected,
        IsInstance,
        LLMJudge,
    )

    PYDANTIC_EVALS_AVAILABLE = True
except ImportError:
    PYDANTIC_EVALS_AVAILABLE = False

    # Create dummy base class for type hints
    class Evaluator:
        pass

    class EvaluatorContext:
        pass


@dataclass
class TraceAwareEvaluator:
    """
    Mixin class for evaluators that inspect execution traces.

    Provides helper methods to extract trace from context metadata or output.
    Subclasses should also inherit from Evaluator and implement evaluate().
    """

    def get_trace(self, ctx: EvaluatorContext) -> dict:
        """
        Extract trace from context.

        Trace can be in:
        1. ctx.metadata['trace'] - if passed via Case metadata
        2. ctx.output['__trace__'] - if returned by task function

        Args:
            ctx: Evaluator context

        Returns:
            Trace dictionary (empty dict if no trace found)
        """
        # Try metadata first
        if hasattr(ctx, "metadata") and ctx.metadata:
            trace = ctx.metadata.get("trace", {})
            if trace:
                return trace

        # Try output
        if isinstance(ctx.output, dict) and "__trace__" in ctx.output:
            return ctx.output["__trace__"]

        return {}

    def get_output(self, ctx: EvaluatorContext) -> Any:
        """
        Extract actual output (without trace wrapper).

        Args:
            ctx: Evaluator context

        Returns:
            Actual output value
        """
        if isinstance(ctx.output, dict) and "__output__" in ctx.output:
            return ctx.output["__output__"]
        return ctx.output


def create_evaluator(config: EvaluatorConfig) -> Evaluator:
    """
    Create a Pydantic Evals evaluator from Tactus config.

    Args:
        config: Tactus evaluator configuration

    Returns:
        Pydantic Evals Evaluator instance

    Raises:
        ValueError: If evaluator type is unknown
        ImportError: If pydantic_evals is not installed
    """
    if not PYDANTIC_EVALS_AVAILABLE:
        raise ImportError("pydantic_evals is required. Install with: pip install pydantic-evals")

    evaluator_type = config.type.lower()

    # Built-in Pydantic Evals evaluators
    if evaluator_type == "contains":
        return _create_contains_evaluator(config)
    elif evaluator_type == "contains_any":
        return _create_contains_any_evaluator(config)
    elif evaluator_type == "equals_expected":
        return _create_equals_expected_evaluator(config)
    elif evaluator_type == "exact_match":
        return _create_equals_expected_evaluator(config)
    elif evaluator_type == "is_instance":
        return _create_is_instance_evaluator(config)
    elif evaluator_type == "llm_judge":
        return _create_llm_judge_evaluator(config)
    elif evaluator_type == "min_length":
        return _create_min_length_evaluator(config)
    elif evaluator_type == "max_length":
        return _create_max_length_evaluator(config)

    # Tactus-specific evaluators
    elif evaluator_type == "max_iterations":
        return _create_max_iterations_evaluator(config)
    elif evaluator_type == "max_cost":
        return _create_max_cost_evaluator(config)
    elif evaluator_type == "max_tokens":
        return _create_max_tokens_evaluator(config)

    # Trace-based evaluators
    elif evaluator_type == "tool_called":
        return _create_tool_called_evaluator(config)
    elif evaluator_type == "state_check":
        return _create_state_check_evaluator(config)
    elif evaluator_type == "agent_turns":
        return _create_agent_turns_evaluator(config)

    # Advanced evaluators
    elif evaluator_type == "regex":
        return _create_regex_evaluator(config)
    elif evaluator_type == "json_schema":
        return _create_json_schema_evaluator(config)
    elif evaluator_type == "range":
        return _create_range_evaluator(config)

    else:
        raise ValueError(f"Unknown evaluator type: {config.type}")


def _create_contains_evaluator(config: EvaluatorConfig) -> Evaluator:
    """Create Contains evaluator."""
    if config.value is None:
        raise ValueError("Contains evaluator requires 'value' field")

    # If a field is specified, create custom evaluator for that field
    if config.field:

        @dataclass
        class FieldContains(Evaluator):
            """Check if specific field contains value."""

            field: str
            value: str
            case_sensitive: bool = True

            def evaluate(self, ctx: EvaluatorContext) -> bool:
                """Check if field contains value."""
                # Get field value
                if isinstance(ctx.output, dict):
                    output = str(ctx.output.get(self.field, ""))
                else:
                    output = str(ctx.output)

                # Check contains
                if self.case_sensitive:
                    return self.value in output
                else:
                    return self.value.lower() in output.lower()

        return FieldContains(
            field=config.field,
            value=config.value,
            case_sensitive=True,
        )

    # Otherwise use standard Contains (checks entire output)
    return Contains(
        value=config.value,
        case_sensitive=True,
    )


def _create_contains_any_evaluator(config: EvaluatorConfig) -> Evaluator:
    """Create custom ContainsAny evaluator that checks for any of multiple values."""

    @dataclass
    class ContainsAny(Evaluator):
        """Check if output contains any of the specified values."""

        field: Optional[str] = None
        check_expected: Optional[str] = None
        values: Optional[list] = None

        def evaluate(self, ctx: EvaluatorContext) -> bool:
            """Check if output contains any of the values."""
            # Get the values to check
            if self.values:
                check_values = self.values
            elif self.check_expected and ctx.expected_output:
                check_values = ctx.expected_output.get(self.check_expected, [])
            else:
                return False

            # Get the output to check
            if self.field and isinstance(ctx.output, dict):
                output = ctx.output.get(self.field, "")
            else:
                output = str(ctx.output)

            # Check if any value is in output
            output_lower = output.lower()
            for value in check_values:
                if str(value).lower() in output_lower:
                    return True
            return False

    return ContainsAny(
        field=config.field,
        check_expected=config.check_expected,
        values=config.value if isinstance(config.value, list) else None,
    )


def _create_equals_expected_evaluator(config: EvaluatorConfig) -> Evaluator:
    """Create EqualsExpected evaluator or field-specific equality check."""

    # If a field is specified, create custom evaluator for that field
    if config.field:

        @dataclass
        class FieldEquals(Evaluator):
            """Check if specific field equals expected value."""

            field: str

            def evaluate(self, ctx: EvaluatorContext) -> bool:
                """Check if field equals expected value."""
                if not ctx.expected_output:
                    return True  # No expected output to compare

                # Get actual field value
                if isinstance(ctx.output, dict):
                    actual = ctx.output.get(self.field)
                else:
                    return False

                # Get expected field value
                expected = ctx.expected_output.get(self.field)

                return actual == expected

        return FieldEquals(field=config.field)

    # Otherwise use standard EqualsExpected (compares entire output)
    return EqualsExpected()


def _create_is_instance_evaluator(config: EvaluatorConfig) -> Evaluator:
    """Create IsInstance evaluator."""
    if config.value is None:
        raise ValueError("IsInstance evaluator requires 'value' field (type name)")

    return IsInstance(type_name=config.value)


def _create_llm_judge_evaluator(config: EvaluatorConfig) -> Evaluator:
    """Create LLMJudge evaluator."""
    if config.rubric is None:
        raise ValueError("LLMJudge evaluator requires 'rubric' field")

    # Note: include_expected is not a standard LLMJudge parameter
    # The rubric itself should specify if comparison is needed
    return LLMJudge(
        rubric=config.rubric,
        model=config.model or "openai:gpt-4o",
        include_input=True,
    )


def _create_min_length_evaluator(config: EvaluatorConfig) -> Evaluator:
    """Create custom MinLength evaluator."""

    @dataclass
    class MinLength(Evaluator):
        """Check if output meets minimum length."""

        field: Optional[str] = None
        min_length: int = 0
        check_expected: Optional[str] = None

        def evaluate(self, ctx: EvaluatorContext) -> bool:
            """Check if output meets minimum length."""
            # Get min_length from expected_output if specified
            min_len = self.min_length
            if self.check_expected and ctx.expected_output:
                min_len = ctx.expected_output.get(self.check_expected, min_len)

            # Get the output to check
            if self.field and isinstance(ctx.output, dict):
                output = ctx.output.get(self.field, "")
            else:
                output = ctx.output

            # Check length
            if isinstance(output, (list, dict)):
                return len(output) >= min_len
            return len(str(output)) >= min_len

    return MinLength(
        field=config.field,
        min_length=config.value or 0,
        check_expected=config.check_expected,
    )


def _create_max_length_evaluator(config: EvaluatorConfig) -> Evaluator:
    """Create custom MaxLength evaluator."""

    @dataclass
    class MaxLength(Evaluator):
        """Check if output doesn't exceed maximum length."""

        field: Optional[str] = None
        max_length: int = 0

        def evaluate(self, ctx: EvaluatorContext) -> bool:
            """Check if output doesn't exceed maximum length."""
            # Get the output to check
            if self.field and isinstance(ctx.output, dict):
                output = ctx.output.get(self.field, "")
            else:
                output = ctx.output

            # Check length
            if isinstance(output, (list, dict)):
                return len(output) <= self.max_length
            return len(str(output)) <= self.max_length

    return MaxLength(
        field=config.field,
        max_length=config.value or 0,
    )


def _create_max_iterations_evaluator(config: EvaluatorConfig) -> Evaluator:
    """Create Tactus-specific MaxIterations evaluator."""

    @dataclass
    class MaxIterations(Evaluator):
        """Check if procedure completed within iteration limit."""

        max_iterations: int

        def evaluate(self, ctx: EvaluatorContext) -> bool:
            """Check if iterations are within limit."""
            # Check metadata for iterations count
            if hasattr(ctx, "metadata") and ctx.metadata:
                iterations = ctx.metadata.get("iterations", 0)
                return iterations <= self.max_iterations

            # Check output for iterations field
            if isinstance(ctx.output, dict):
                iterations = ctx.output.get("iterations", 0)
                return iterations <= self.max_iterations

            return True  # Pass if we can't find iterations

    return MaxIterations(max_iterations=config.value or 10)


def _create_max_cost_evaluator(config: EvaluatorConfig) -> Evaluator:
    """Create Tactus-specific MaxCost evaluator."""

    @dataclass
    class MaxCost(Evaluator):
        """Check if procedure cost is within budget."""

        max_cost: float

        def evaluate(self, ctx: EvaluatorContext) -> bool:
            """Check if cost is within budget."""
            # Check metadata for cost
            if hasattr(ctx, "metadata") and ctx.metadata:
                cost = ctx.metadata.get("total_cost", 0.0)
                return cost <= self.max_cost

            # Check output for cost field
            if isinstance(ctx.output, dict):
                cost = ctx.output.get("total_cost", 0.0)
                return cost <= self.max_cost

            return True  # Pass if we can't find cost

    return MaxCost(max_cost=config.value or 1.0)


def _create_max_tokens_evaluator(config: EvaluatorConfig) -> Evaluator:
    """Create Tactus-specific MaxTokens evaluator."""

    @dataclass
    class MaxTokens(Evaluator):
        """Check if token usage is within limit."""

        max_tokens: int

        def evaluate(self, ctx: EvaluatorContext) -> bool:
            """Check if tokens are within limit."""
            # Check metadata for tokens
            if hasattr(ctx, "metadata") and ctx.metadata:
                tokens = ctx.metadata.get("total_tokens", 0)
                return tokens <= self.max_tokens

            # Check output for tokens field
            if isinstance(ctx.output, dict):
                tokens = ctx.output.get("total_tokens", 0)
                return tokens <= self.max_tokens

            return True  # Pass if we can't find tokens

    return MaxTokens(max_tokens=config.value or 10000)


def _create_tool_called_evaluator(config: EvaluatorConfig) -> Evaluator:
    """Create evaluator that checks if specific tool was called."""

    @dataclass
    class ToolCalled(TraceAwareEvaluator, Evaluator):
        """Check if tool was called during execution."""

        tool_name: str
        min_calls: int = 1
        max_calls: Optional[int] = None

        def evaluate(self, ctx: EvaluatorContext) -> bool:
            """Check if tool was called the expected number of times."""
            trace = self.get_trace(ctx)
            tool_calls = trace.get("tool_calls", [])

            # Count calls to this tool
            count = sum(1 for call in tool_calls if call.get("name") == self.tool_name)

            if count < self.min_calls:
                return False
            if self.max_calls is not None and count > self.max_calls:
                return False
            return True

    return ToolCalled(
        tool_name=config.value,
        min_calls=getattr(config, "min_value", None) or 1,
        max_calls=getattr(config, "max_value", None),
    )


def _create_state_check_evaluator(config: EvaluatorConfig) -> Evaluator:
    """Create evaluator that checks state variable values."""

    @dataclass
    class StateCheck(TraceAwareEvaluator, Evaluator):
        """Check if state variable has expected value."""

        variable: str
        expected_value: Any

        def evaluate(self, ctx: EvaluatorContext) -> bool:
            """Check if state variable matches expected value."""
            trace = self.get_trace(ctx)
            state_changes = trace.get("state_changes", [])

            # Find final value of variable
            for change in reversed(state_changes):
                if isinstance(change, dict) and change.get("variable") == self.variable:
                    return change.get("value") == self.expected_value

            return False

    return StateCheck(variable=config.field or "", expected_value=config.value)


def _create_agent_turns_evaluator(config: EvaluatorConfig) -> Evaluator:
    """Create evaluator that checks agent turn counts."""

    @dataclass
    class AgentTurns(TraceAwareEvaluator, Evaluator):
        """Check number of agent turns."""

        agent_name: Optional[str] = None
        min_turns: int = 1
        max_turns: Optional[int] = None

        def evaluate(self, ctx: EvaluatorContext) -> bool:
            """Check if agent turn count is within expected range."""
            trace = self.get_trace(ctx)
            agent_turns = trace.get("agent_turns", [])

            # Filter by agent if specified
            if self.agent_name:
                agent_turns = [t for t in agent_turns if t.get("agent") == self.agent_name]

            count = len(agent_turns)
            if count < self.min_turns:
                return False
            if self.max_turns is not None and count > self.max_turns:
                return False
            return True

    return AgentTurns(
        agent_name=config.field,
        min_turns=getattr(config, "min_value", None) or 1,
        max_turns=getattr(config, "max_value", None),
    )


def _create_regex_evaluator(config: EvaluatorConfig) -> Evaluator:
    """Create evaluator that matches output against regex pattern."""
    import re

    @dataclass
    class RegexMatch(Evaluator):
        """Check if output matches regex pattern."""

        field: Optional[str] = None
        pattern: str = ""
        case_sensitive: bool = True

        def evaluate(self, ctx: EvaluatorContext) -> bool:
            """Check if output matches the regex pattern."""
            # Get output
            if self.field and isinstance(ctx.output, dict):
                output = str(ctx.output.get(self.field, ""))
            else:
                output = str(ctx.output)

            # Match pattern
            flags = 0 if self.case_sensitive else re.IGNORECASE
            return bool(re.search(self.pattern, output, flags))

    return RegexMatch(
        field=config.field,
        pattern=config.value or "",
        case_sensitive=getattr(config, "case_sensitive", True),
    )


def _create_json_schema_evaluator(config: EvaluatorConfig) -> Evaluator:
    """Create evaluator that validates output against JSON schema."""

    @dataclass
    class JSONSchemaValidator(Evaluator):
        """Validate output against JSON schema."""

        field: Optional[str] = None
        schema: dict = None

        def evaluate(self, ctx: EvaluatorContext) -> bool:
            """Validate output against JSON schema."""
            try:
                from jsonschema import validate, ValidationError
            except ImportError:
                logger.warning("jsonschema not installed, skipping validation")
                return True

            # Get output
            if self.field and isinstance(ctx.output, dict):
                output = ctx.output.get(self.field)
            else:
                output = ctx.output

            # Validate
            try:
                validate(instance=output, schema=self.schema)
                return True
            except ValidationError:
                return False

    return JSONSchemaValidator(field=config.field, schema=config.json_schema or config.value or {})


def _create_range_evaluator(config: EvaluatorConfig) -> Evaluator:
    """Create evaluator that checks if numeric value is within range."""

    @dataclass
    class NumericRange(Evaluator):
        """Check if numeric output is within range."""

        field: Optional[str] = None
        min_value: Optional[float] = None
        max_value: Optional[float] = None

        def evaluate(self, ctx: EvaluatorContext) -> bool:
            """Check if value is within numeric range."""
            # Get output
            if self.field and isinstance(ctx.output, dict):
                value = ctx.output.get(self.field)
            else:
                value = ctx.output

            # Convert to float
            try:
                num = float(value)
            except (ValueError, TypeError):
                return False

            # Check range
            if self.min_value is not None and num < self.min_value:
                return False
            if self.max_value is not None and num > self.max_value:
                return False
            return True

    # Extract min/max from value dict or use separate fields
    if isinstance(config.value, dict):
        min_val = config.value.get("min")
        max_val = config.value.get("max")
    else:
        min_val = getattr(config, "min_value", None)
        max_val = getattr(config, "max_value", None)

    return NumericRange(field=config.field, min_value=min_val, max_value=max_val)
