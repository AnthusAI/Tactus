"""
Retry Primitive - Error handling with exponential backoff.

Provides:
- Retry.with_backoff(fn, options) - Retry function with exponential backoff
"""

import logging
import time
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


class RetryPrimitive:
    """
    Handles retry logic with exponential backoff for procedures.

    Enables workflows to:
    - Retry failed operations automatically
    - Use exponential backoff between attempts
    - Handle transient errors gracefully
    - Configure max attempts and delays
    """

    def __init__(self):
        """Initialize Retry primitive."""
        logger.debug("RetryPrimitive initialized")

    def with_backoff(
        self, function_to_retry: Callable, options: Optional[dict[str, Any]] = None
    ) -> Any:
        """
        Retry a function with exponential backoff.

        Args:
            function_to_retry: Function to retry (Lua function)
            options: Dict with:
                - max_attempts: Maximum retry attempts (default: 3)
                - initial_delay: Initial delay in seconds (default: 1)
                - max_delay: Maximum delay in seconds (default: 60)
                - backoff_factor: Multiplier for delay (default: 2)
                - on_error: Optional callback when error occurs

        Returns:
            Result from successful function call

        Raises:
            Exception: If all retry attempts fail

        Example (Lua):
            local result = Retry.with_backoff(function()
                -- Try to fetch data from API
                local data = fetch_api_data()
                if not data then
                    error("API returned no data")
                end
                return data
            end, {
                max_attempts = 5,
                initial_delay = 2,
                backoff_factor = 2
            })
        """
        # Convert Lua tables to Python dicts if needed
        options_dict = self._convert_lua_to_python(options) or {}

        max_attempts = options_dict.get("max_attempts", 3)
        initial_delay = options_dict.get("initial_delay", 1.0)
        max_delay = options_dict.get("max_delay", 60.0)
        backoff_factor = options_dict.get("backoff_factor", 2.0)
        on_error = options_dict.get("on_error")

        attempt_number = 0
        current_delay = initial_delay
        last_error = None

        logger.info("Starting retry with_backoff (max_attempts=%s)", max_attempts)

        while attempt_number < max_attempts:
            attempt_number += 1

            try:
                logger.debug("Retry attempt %s/%s", attempt_number, max_attempts)
                result = function_to_retry()
                logger.info("Success on attempt %s/%s", attempt_number, max_attempts)
                return result

            except Exception as error:
                last_error = error
                logger.warning("Attempt %s/%s failed: %s", attempt_number, max_attempts, error)

                # Call error callback if provided
                if on_error and callable(on_error):
                    try:
                        on_error(
                            {
                                "attempt": attempt_number,
                                "max_attempts": max_attempts,
                                "error": str(error),
                                "delay": current_delay,
                            }
                        )
                    except Exception as callback_error:
                        logger.error("Error callback failed: %s", callback_error)

                # Check if we should retry
                if attempt_number >= max_attempts:
                    logger.error("All %s attempts failed", max_attempts)
                    raise Exception(f"Retry failed after {max_attempts} attempts: {last_error}")

                # Wait with exponential backoff
                logger.info("Waiting %.2fs before retry...", current_delay)
                time.sleep(current_delay)

                # Increase delay for next attempt (exponential backoff)
                current_delay = min(current_delay * backoff_factor, max_delay)

        # Should not reach here, but handle it
        raise Exception(f"Retry logic error: {last_error}")

    def _convert_lua_to_python(self, value: Any) -> Any:
        """
        Recursively convert Lua tables to Python dicts.

        Args:
            value: Lua value to convert

        Returns:
            Python equivalent (dict or primitive)
        """
        if value is None:
            return None

        # Import lupa for table checking
        try:
            from lupa import lua_type

            # Check if it's a Lua table
            if lua_type(value) == "table":
                result = {}
                for k, v in value.items():
                    # Convert key and value recursively
                    py_key = self._convert_lua_to_python(k) if lua_type(k) == "table" else k
                    py_value = self._convert_lua_to_python(v)
                    result[py_key] = py_value
                return result
            else:
                # Primitive value or function
                return value

        except ImportError:
            # If lupa not available, just return as-is
            return value

    def __repr__(self) -> str:
        return "RetryPrimitive()"
