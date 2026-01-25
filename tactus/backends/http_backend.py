"""
HTTP model backend for REST endpoint inference.
"""

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class HTTPModelBackend:
    """Model backend that calls HTTP REST endpoints."""

    def __init__(self, endpoint: str, timeout: float = 30.0, headers: dict | None = None):
        """
        Initialize HTTP model backend.

        Args:
            endpoint: URL of the inference endpoint
            timeout: Request timeout in seconds
            headers: Optional HTTP headers to include
        """
        self.endpoint = endpoint
        self.timeout = timeout
        self.headers = headers or {}

    async def predict(self, input_data: Any) -> Any:
        """
        Call HTTP endpoint with input data.

        Args:
            input_data: Data to send to endpoint (will be JSON serialized)

        Returns:
            Response JSON from endpoint
        """
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(self.endpoint, json=input_data, headers=self.headers)
            response.raise_for_status()
            return response.json()

    def predict_sync(self, input_data: Any) -> Any:
        """
        Synchronous version of predict.

        Args:
            input_data: Data to send to endpoint (will be JSON serialized)

        Returns:
            Response JSON from endpoint
        """
        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(self.endpoint, json=input_data, headers=self.headers)
            response.raise_for_status()
            return response.json()
