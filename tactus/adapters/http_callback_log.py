"""
HTTP Callback Log Handler for container event streaming.

Posts log events to a callback URL for real-time streaming from containers.
Used when TACTUS_CALLBACK_URL environment variable is set.
"""

import logging
import os
from typing import Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from tactus.protocols.models import LogEvent, CostEvent

logger = logging.getLogger(__name__)


class HTTPCallbackLogHandler:
    """
    Log handler that POSTs events to an HTTP callback URL.

    Used inside Docker containers to stream events back to the IDE backend.
    The callback URL is provided via TACTUS_CALLBACK_URL environment variable.
    """

    def __init__(
        self,
        callback_url: str,
        timeout: float = 5.0,
        max_retries: int = 3,
    ):
        """
        Initialize HTTP callback log handler.

        Args:
            callback_url: URL to POST events to
            timeout: Request timeout in seconds
            max_retries: Number of retries on failure
        """
        self.callback_url = callback_url
        self.timeout = timeout
        self.cost_events: list[CostEvent] = []  # Track cost events for aggregation

        # Setup session with retry logic
        self.session = requests.Session()
        retry_strategy = Retry(
            total=max_retries,
            backoff_factor=0.1,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

        logger.info("[HTTP_CALLBACK] Initialized with URL: %s", callback_url)

    def log(self, event: LogEvent) -> None:
        """
        POST log event to callback URL.

        Args:
            event: Structured log event
        """
        # Track cost events for aggregation (mirrors IDELogHandler behavior)
        if isinstance(event, CostEvent):
            self.cost_events.append(event)

        try:
            # Serialize event to JSON
            event_payload = event.model_dump(mode="json")

            # Format timestamp to ensure ISO format with Z suffix
            iso_string = event.timestamp.isoformat()
            has_timezone_marker = (
                iso_string.endswith("Z") or "+" in iso_string or iso_string.count("-") > 2
            )
            if not has_timezone_marker:
                iso_string += "Z"
            event_payload["timestamp"] = iso_string

            # POST to callback URL
            response = self.session.post(
                self.callback_url,
                json=event_payload,
                timeout=self.timeout,
            )
            response.raise_for_status()
            logger.debug("[HTTP_CALLBACK] Event posted: type=%s", event.event_type)

        except requests.exceptions.RequestException as error:
            # Log but don't fail - event streaming is best-effort
            logger.warning(
                "[HTTP_CALLBACK] Failed to POST event to %s: %s",
                self.callback_url,
                error,
            )
        except Exception as error:
            # Catch any other errors to prevent crashing the procedure
            logger.warning("[HTTP_CALLBACK] Unexpected error posting event: %s", error)

    @classmethod
    def from_environment(cls) -> Optional["HTTPCallbackLogHandler"]:
        """
        Create handler from TACTUS_CALLBACK_URL environment variable.

        Returns:
            HTTPCallbackLogHandler if env var is set, None otherwise.
        """
        callback_url = os.environ.get("TACTUS_CALLBACK_URL")
        if callback_url:
            logger.info(
                "[HTTP_CALLBACK] Creating handler from environment: %s",
                callback_url,
            )
            return cls(callback_url=callback_url)
        return None
