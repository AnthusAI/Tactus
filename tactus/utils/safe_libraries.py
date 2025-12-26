"""
Safe Lua standard library implementations with determinism warnings.

Provides wrapped versions of math.random, os.time, os.date, os.clock that
warn when used outside checkpoint boundaries to prevent replay bugs in
Tactus's checkpoint-and-replay execution system.
"""

import warnings
import time
import random
import math
from datetime import datetime
from typing import Callable, Any, Optional
from functools import wraps


class DeterminismWarning(UserWarning):
    """Warning issued when non-deterministic function called outside checkpoint."""

    pass


class NonDeterministicError(Exception):
    """Raised in strict mode when non-deterministic function called outside checkpoint."""

    pass


def warn_if_unsafe(operation_name: str, get_context: Callable[[], Optional[Any]]):
    """
    Decorator that warns when non-deterministic operation used outside checkpoint.

    Args:
        operation_name: Human-readable name of operation (e.g., "math.random()")
        get_context: Callback to retrieve current ExecutionContext

    Returns:
        Decorated function that checks checkpoint scope
    """

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Get context via callback
            context = get_context()

            # If no context, can't enforce (allow silently for REPL/testing)
            if context is None:
                return func(*args, **kwargs)

            # Check if inside checkpoint
            inside_checkpoint = getattr(context, "_inside_checkpoint", False)

            if not inside_checkpoint:
                message = (
                    f"\n{'=' * 70}\n"
                    f"DETERMINISM WARNING: {operation_name} called outside checkpoint\n"
                    f"{'=' * 70}\n\n"
                    f"Non-deterministic operations must be wrapped in checkpoints "
                    f"for durability.\n\n"
                    f"To fix, wrap your code in a checkpoint:\n\n"
                    f"  -- Lua example:\n"
                    f"  local random_value = Step.checkpoint(function()\n"
                    f"    return {operation_name}\n"
                    f"  end)\n\n"
                    f"Or use checkpoint() directly:\n\n"
                    f"  local result = checkpoint(function()\n"
                    f"    -- Your non-deterministic code here\n"
                    f"    return {operation_name}\n"
                    f"  end)\n\n"
                    f"Why: Tactus uses checkpointing for durable execution. "
                    f"Operations outside\n"
                    f"checkpoints may produce different results on replay, "
                    f"breaking determinism.\n"
                    f"\n{'=' * 70}\n"
                )

                # Check strict mode
                strict_mode = getattr(context, "strict_determinism", False)

                if strict_mode:
                    raise NonDeterministicError(message)
                else:
                    # Use stacklevel=4 to point to Lua code, not wrapper
                    warnings.warn(message, DeterminismWarning, stacklevel=4)

            return func(*args, **kwargs)

        return wrapper

    return decorator


def create_safe_math_library(get_context: Callable, strict_mode: bool = False):
    """
    Create safe math library with warnings for random functions.

    Args:
        get_context: Callback returning current ExecutionContext
        strict_mode: If True, raise errors instead of warnings (not currently used - context has it)

    Returns:
        Dict with safe math functions (keys are strings for Lua table)
    """

    @warn_if_unsafe("math.random()", get_context)
    def safe_random(m=None, n=None):
        """
        Safe math.random() with checkpoint warning.

        Lua's math.random() has three forms:
        - math.random(): returns float in [0, 1)
        - math.random(n): returns integer in [1, n]
        - math.random(m, n): returns integer in [m, n]
        """
        if m is None and n is None:
            # No arguments: return float [0, 1)
            return random.random()
        elif n is None:
            # One argument: return integer [1, m]
            return random.randint(1, int(m))
        else:
            # Two arguments: return integer [m, n]
            return random.randint(int(m), int(n))

    @warn_if_unsafe("math.randomseed()", get_context)
    def safe_randomseed(seed):
        """Safe math.randomseed() with checkpoint warning."""
        random.seed(int(seed))
        return None

    # Standard math functions (deterministic - pass through)
    return {
        # Deterministic functions - safe to use anywhere
        "abs": abs,
        "acos": math.acos,
        "asin": math.asin,
        "atan": math.atan,
        "atan2": math.atan2,
        "ceil": math.ceil,
        "cos": math.cos,
        "cosh": math.cosh,
        "deg": math.degrees,
        "exp": math.exp,
        "floor": math.floor,
        "fmod": math.fmod,
        "huge": float("inf"),
        "log": math.log,
        "log10": math.log10,
        "max": max,
        "min": min,
        "modf": math.modf,
        "pi": math.pi,
        "pow": pow,
        "rad": math.radians,
        "sin": math.sin,
        "sinh": math.sinh,
        "sqrt": math.sqrt,
        "tan": math.tan,
        "tanh": math.tanh,
        # Non-deterministic functions (wrapped with warnings)
        "random": safe_random,
        "randomseed": safe_randomseed,
    }


def create_safe_os_library(get_context: Callable, strict_mode: bool = False):
    """
    Create safe os library with warnings for non-deterministic functions.

    Args:
        get_context: Callback returning current ExecutionContext
        strict_mode: If True, raise errors instead of warnings (not currently used - context has it)

    Returns:
        Dict with safe os functions
    """

    @warn_if_unsafe("os.time()", get_context)
    def safe_time(date_table=None):
        """Safe os.time() with checkpoint warning."""
        if date_table is None:
            return int(time.time())
        else:
            # Lua date table format: {year, month, day, hour, min, sec}
            # For simplicity, just return current time
            # Full implementation would parse the table
            return int(time.time())

    @warn_if_unsafe("os.date()", get_context)
    def safe_date(format_str=None):
        """Safe os.date() with checkpoint warning."""
        now = datetime.utcnow()

        if format_str is None:
            # Default format like Lua's os.date()
            return now.strftime("%a %b %d %H:%M:%S %Y")
        elif format_str == "%Y-%m-%dT%H:%M:%SZ":
            # ISO 8601 format
            return now.strftime("%Y-%m-%dT%H:%M:%SZ")
        else:
            # Support Python strftime formats
            try:
                return now.strftime(format_str)
            except Exception:
                return now.strftime("%a %b %d %H:%M:%S %Y")

    @warn_if_unsafe("os.clock()", get_context)
    def safe_clock():
        """Safe os.clock() with checkpoint warning."""
        return time.process_time()

    @warn_if_unsafe("os.getenv()", get_context)
    def safe_getenv(varname):
        """Safe os.getenv() with checkpoint warning - environment variables can change."""
        import os

        return os.getenv(varname)

    @warn_if_unsafe("os.tmpname()", get_context)
    def safe_tmpname():
        """Safe os.tmpname() with checkpoint warning - generates unique temporary filenames."""
        import tempfile

        return tempfile.mktemp()

    return {
        "time": safe_time,
        "date": safe_date,
        "clock": safe_clock,
        "getenv": safe_getenv,
        "tmpname": safe_tmpname,
    }
