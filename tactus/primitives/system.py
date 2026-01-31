"""
System Primitive - non-blocking operational alerts.

Provides:
- System.alert(opts) - Emit structured alert event (non-blocking)
"""

from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


class SystemPrimitive:
    """System-level primitives that are safe to call from anywhere."""

    _ALLOWED_LEVELS = {"info", "warning", "error", "critical"}

    def __init__(self, procedure_id: Optional[str] = None, log_handler: Any = None):
        self.procedure_id = procedure_id
        self.log_handler = log_handler

    def _lua_to_python(self, value: Any) -> Any:
        """Convert Lua objects to Python equivalents recursively."""
        if value is None:
            return None
        if hasattr(value, "items") and not isinstance(value, dict):
            return {k: self._lua_to_python(v) for k, v in value.items()}
        if isinstance(value, dict):
            return {k: self._lua_to_python(v) for k, v in value.items()}
        if isinstance(value, (list, tuple)):
            return [self._lua_to_python(v) for v in value]
        return value

    def alert(self, options: Optional[dict[str, Any]] = None) -> None:
        """
        Emit a system alert (NON-BLOCKING).

        Args:
            options: Dict with:
                - message: str - Alert message (required)
                - level: str - info, warning, error, critical (default: info)
                - source: str - Where the alert originated (optional)
                - context: Dict - Additional structured context (optional)
        """
        options_dict = self._lua_to_python(options) or {}

        message = str(options_dict.get("message", "Alert"))
        level = str(options_dict.get("level", "info")).lower()
        source = options_dict.get("source")
        context = options_dict.get("context") or {}

        if level not in self._ALLOWED_LEVELS:
            raise ValueError(
                f"Invalid alert level '{level}'. Allowed levels: {sorted(self._ALLOWED_LEVELS)}"
            )

        # Emit structured event if possible (preferred for CLI/IDE)
        if self.log_handler:
            try:
                from tactus.protocols.models import SystemAlertEvent

                event = SystemAlertEvent(
                    level=level,
                    message=message,
                    source=str(source) if source is not None else None,
                    context=context if isinstance(context, dict) else {"context": context},
                    procedure_id=self.procedure_id,
                )
                self.log_handler.log(event)
                return
            except Exception as error:  # pragma: no cover
                logger.warning("Failed to emit SystemAlertEvent: %s", error)

        # Fallback to standard logging
        python_level = {
            "info": logging.INFO,
            "warning": logging.WARNING,
            "error": logging.ERROR,
            "critical": logging.CRITICAL,
        }[level]

        origin = f" source={source}" if source is not None else ""
        if context:
            logger.log(
                python_level,
                "System.alert [%s]%s: %s | %s",
                level,
                origin,
                message,
                context,
            )
        else:
            logger.log(
                python_level,
                "System.alert [%s]%s: %s",
                level,
                origin,
                message,
            )

    def __repr__(self) -> str:
        return f"SystemPrimitive(procedure_id={self.procedure_id})"
