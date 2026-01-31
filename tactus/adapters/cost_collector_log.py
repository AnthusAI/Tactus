"""
Cost-only log handler for headless/sandbox runs.

Collects CostEvent instances so the runtime can report total_cost/total_tokens,
without enabling streaming UI behavior.
"""

from __future__ import annotations

import json
import logging

from tactus.protocols.models import CostEvent, LogEvent

logger = logging.getLogger(__name__)


class CostCollectorLogHandler:
    """
    Minimal LogHandler for sandbox runs.

    This is useful in environments like Docker sandboxes where stdout is reserved
    for protocol output, but we still want:
    - accurate cost accounting (CostEvent)
    - basic procedure logging (LogEvent) via stderr/Python logging
    """

    supports_streaming = False

    def __init__(self):
        self.cost_events: list[CostEvent] = []
        logger.debug("CostCollectorLogHandler initialized")

    def log(self, event: LogEvent) -> None:
        if isinstance(event, CostEvent):
            self.cost_events.append(event)
            return

        # Preserve useful procedure logs even when no IDE callback is present.
        if isinstance(event, LogEvent):
            event_logger = logging.getLogger(event.logger_name or "procedure")

            message_text = event.message
            if event.context:
                context_json = json.dumps(event.context, indent=2, default=str)
                message_text = f"{message_text}\nContext: {context_json}"

            level = (event.level or "INFO").upper()
            if level == "DEBUG":
                event_logger.debug(message_text)
            elif level in ("WARN", "WARNING"):
                event_logger.warning(message_text)
            elif level == "ERROR":
                event_logger.error(message_text)
            else:
                event_logger.info(message_text)
