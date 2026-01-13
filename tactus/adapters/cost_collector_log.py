"""
Cost-only log handler for headless/sandbox runs.

Collects CostEvent instances so the runtime can report total_cost/total_tokens,
without enabling streaming UI behavior.
"""

from __future__ import annotations

import logging
import json
from typing import List

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
        self.cost_events: List[CostEvent] = []
        logger.debug("CostCollectorLogHandler initialized")

    def log(self, event: LogEvent) -> None:
        if isinstance(event, CostEvent):
            self.cost_events.append(event)
            return

        # Preserve useful procedure logs even when no IDE callback is present.
        if isinstance(event, LogEvent):
            event_logger = logging.getLogger(event.logger_name or "procedure")

            msg = event.message
            if event.context:
                msg = f"{msg}\nContext: {json.dumps(event.context, indent=2, default=str)}"

            level = (event.level or "INFO").upper()
            if level == "DEBUG":
                event_logger.debug(msg)
            elif level in ("WARN", "WARNING"):
                event_logger.warning(msg)
            elif level == "ERROR":
                event_logger.error(msg)
            else:
                event_logger.info(msg)
