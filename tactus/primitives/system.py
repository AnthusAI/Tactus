"""
System Primitive - non-blocking operational alerts.

Provides:
- System.alert(opts) - Emit structured alert event (non-blocking)
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional


logger = logging.getLogger(__name__)


class SystemPrimitive:
    """System-level primitives that are safe to call from anywhere."""

    _ALLOWED_LEVELS = {"info", "warning", "error", "critical"}

    def __init__(self, procedure_id: Optional[str] = None, log_handler: Any = None):
        self.procedure_id = procedure_id
        self.log_handler = log_handler

    def _lua_to_python(self, obj: Any) -> Any:
        """Convert Lua objects to Python equivalents recursively."""
        if obj is None:
            return None
        if hasattr(obj, "items") and not isinstance(obj, dict):
            return {k: self._lua_to_python(v) for k, v in obj.items()}
        if isinstance(obj, dict):
            return {k: self._lua_to_python(v) for k, v in obj.items()}
        if isinstance(obj, (list, tuple)):
            return [self._lua_to_python(v) for v in obj]
        return obj

    def alert(self, options: Optional[Dict[str, Any]] = None) -> None:
        """
        Emit a system alert (NON-BLOCKING).

        Args:
            options: Dict with:
                - message: str - Alert message (required)
                - level: str - info, warning, error, critical (default: info)
                - source: str - Where the alert originated (optional)
                - context: Dict - Additional structured context (optional)
        """
        opts = self._lua_to_python(options) or {}

        message = str(opts.get("message", "Alert"))
        level = str(opts.get("level", "info")).lower()
        source = opts.get("source")
        context = opts.get("context") or {}

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
            except Exception as e:  # pragma: no cover
                logger.warning(f"Failed to emit SystemAlertEvent: {e}")

        # Fallback to standard logging
        python_level = {
            "info": logging.INFO,
            "warning": logging.WARNING,
            "error": logging.ERROR,
            "critical": logging.CRITICAL,
        }[level]

        origin = f" source={source}" if source is not None else ""
        if context:
            logger.log(python_level, f"System.alert [{level}]{origin}: {message} | {context}")
        else:
            logger.log(python_level, f"System.alert [{level}]{origin}: {message}")

    def __repr__(self) -> str:
        return f"SystemPrimitive(procedure_id={self.procedure_id})"
