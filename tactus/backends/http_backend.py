"""
HTTP model backend for REST endpoint inference.
"""

import logging
from typing import Any, Dict, Optional

import httpx

logger = logging.getLogger(__name__)


class HTTPModelBackend:
    """Model backend that calls HTTP REST endpoints."""

    def __init__(
        self,
        endpoint: str,
        timeout: float = 30.0,
        headers: Optional[Dict] = None,
        cost_per_call: Optional[float] = None,
    ):
        """
        Initialize HTTP model backend.

        Args:
            endpoint: URL of the inference endpoint
            timeout: Request timeout in seconds
            headers: Optional HTTP headers to include
            cost_per_call: Optional cost in dollars per prediction call
        """
        self.endpoint = endpoint
        self.timeout = timeout
        self.headers = headers or {}
        self.cost_per_call = cost_per_call

    async def predict(self, input_data: Any) -> Any:
        """
        Call HTTP endpoint with input data.

        Args:
            input_data: Data to send to endpoint (will be JSON serialized)

        Returns:
            Response JSON from endpoint, wrapped with cost if cost_per_call is set
        """
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(self.endpoint, json=input_data, headers=self.headers)
            response.raise_for_status()
            result = response.json()

            # If cost tracking is enabled, wrap result in cost format
            if self.cost_per_call is not None:
                return {
                    "result": result,
                    "cost": {
                        "total_cost": self.cost_per_call,
                        "prompt_cost": self.cost_per_call,  # For HTTP, all cost is "prompt"
                        "completion_cost": 0.0,
                    },
                    "usage": {
                        "prompt_tokens": 0,
                        "completion_tokens": 0,
                        "total_tokens": 0,
                    },
                }
            return result

    def predict_sync(self, input_data: Any) -> Any:
        """
        Synchronous version of predict.

        Args:
            input_data: Data to send to endpoint (will be JSON serialized)

        Returns:
            Response JSON from endpoint, wrapped with cost if cost_per_call is set
        """
        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(self.endpoint, json=input_data, headers=self.headers)
            response.raise_for_status()
            result = response.json()

            # If cost tracking is enabled, wrap result in cost format
            if self.cost_per_call is not None:
                return {
                    "result": result,
                    "cost": {
                        "total_cost": self.cost_per_call,
                        "prompt_cost": self.cost_per_call,  # For HTTP, all cost is "prompt"
                        "completion_cost": 0.0,
                    },
                    "usage": {
                        "prompt_tokens": 0,
                        "completion_tokens": 0,
                        "total_tokens": 0,
                    },
                }
            return result
