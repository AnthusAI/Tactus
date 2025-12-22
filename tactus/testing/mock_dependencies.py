"""
Mock implementations of dependencies for testing.

Provides fake HTTP clients, databases, etc. that can be used in BDD tests
without making real network calls or database connections.
"""

import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class MockResponse:
    """Mock HTTP response."""

    text: str
    status_code: int = 200
    headers: Dict[str, str] = None

    def __post_init__(self):
        if self.headers is None:
            self.headers = {}

    def json(self):
        """Parse response as JSON."""
        import json

        return json.loads(self.text)


class MockHTTPClient:
    """
    Mock HTTP client that returns pre-configured responses.

    Used in tests to avoid making real HTTP calls.
    """

    def __init__(self, responses: Optional[Dict[str, str]] = None):
        """
        Initialize mock HTTP client.

        Args:
            responses: Dict mapping path to response text
                      e.g., {"/weather": '{"temp": 72}'}
        """
        self.responses = responses or {}
        self.calls: List[tuple] = []  # Track all calls for assertions
        self.base_url = None

    def add_response(self, path: str, response: str, status_code: int = 200):
        """Add a mock response for a specific path."""
        self.responses[path] = {"text": response, "status_code": status_code}
        logger.debug(f"Added mock response for {path}")

    async def get(self, path: str, **kwargs) -> MockResponse:
        """Mock GET request."""
        self.calls.append(("GET", path, kwargs))
        logger.debug(f"Mock HTTP GET: {path}")

        if path in self.responses:
            response_data = self.responses[path]
            if isinstance(response_data, dict):
                return MockResponse(
                    text=response_data.get("text", ""),
                    status_code=response_data.get("status_code", 200),
                )
            else:
                return MockResponse(text=response_data)

        # Default response if no mock configured
        return MockResponse(text="{}", status_code=200)

    async def post(self, path: str, **kwargs) -> MockResponse:
        """Mock POST request."""
        self.calls.append(("POST", path, kwargs))
        logger.debug(f"Mock HTTP POST: {path}")

        if path in self.responses:
            response_data = self.responses[path]
            if isinstance(response_data, dict):
                return MockResponse(
                    text=response_data.get("text", ""),
                    status_code=response_data.get("status_code", 200),
                )
            else:
                return MockResponse(text=response_data)

        return MockResponse(text="{}", status_code=200)

    async def aclose(self):
        """Mock close method (does nothing)."""
        logger.debug("Mock HTTP client closed")
        pass

    def get_calls(self) -> List[tuple]:
        """Get all calls made to this client."""
        return self.calls

    def was_called(self, method: str = None, path: str = None) -> bool:
        """Check if a specific call was made."""
        for call_method, call_path, _ in self.calls:
            if method and method != call_method:
                continue
            if path and path != call_path:
                continue
            return True
        return False


class MockDatabase:
    """
    Mock database connection for testing.

    Stores data in memory instead of making real database calls.
    """

    def __init__(self):
        self.data: Dict[str, Any] = {}
        self.queries: List[str] = []

    async def execute(self, query: str, *args) -> Any:
        """Mock query execution."""
        self.queries.append(query)
        logger.debug(f"Mock DB execute: {query}")
        return None

    async def fetch(self, query: str, *args) -> List[Dict]:
        """Mock fetch (returns empty list)."""
        self.queries.append(query)
        logger.debug(f"Mock DB fetch: {query}")
        return []

    async def close(self):
        """Mock close."""
        logger.debug("Mock database closed")
        pass


class MockRedis:
    """
    Mock Redis client for testing.

    Stores data in memory dictionary.
    """

    def __init__(self):
        self.store: Dict[str, Any] = {}

    async def get(self, key: str) -> Optional[str]:
        """Mock get."""
        return self.store.get(key)

    async def set(self, key: str, value: Any):
        """Mock set."""
        self.store[key] = value
        logger.debug(f"Mock Redis SET: {key}")

    async def delete(self, key: str):
        """Mock delete."""
        if key in self.store:
            del self.store[key]
            logger.debug(f"Mock Redis DEL: {key}")

    async def close(self):
        """Mock close."""
        logger.debug("Mock Redis closed")
        pass


class MockDependencyFactory:
    """
    Factory for creating mock dependencies instead of real ones.

    Used by test infrastructure to inject mocks.
    """

    @staticmethod
    async def create_mock(
        resource_type: str, config: Dict[str, Any], mock_responses: Optional[Dict] = None
    ) -> Any:
        """
        Create a mock dependency.

        Args:
            resource_type: Type of resource (http_client, postgres, redis)
            config: Configuration dict (mostly ignored for mocks)
            mock_responses: Optional dict of mock responses for HTTP client

        Returns:
            Mock resource instance
        """
        if resource_type == "http_client":
            mock_client = MockHTTPClient(mock_responses)
            mock_client.base_url = config.get("base_url")
            return mock_client

        elif resource_type == "postgres":
            return MockDatabase()

        elif resource_type == "redis":
            return MockRedis()

        else:
            raise ValueError(f"Unknown resource type: {resource_type}")

    @staticmethod
    async def create_all_mocks(
        dependencies_config: Dict[str, Dict[str, Any]],
        mock_responses: Optional[Dict[str, Dict]] = None,
    ) -> Dict[str, Any]:
        """
        Create all mock dependencies.

        Args:
            dependencies_config: Dict mapping dependency name to config
            mock_responses: Optional dict mapping dependency name to mock responses

        Returns:
            Dict mapping dependency name to mock resource
        """
        mocks = {}

        for dep_name, dep_config in dependencies_config.items():
            resource_type = dep_config.get("type")
            responses = mock_responses.get(dep_name) if mock_responses else None

            mock = await MockDependencyFactory.create_mock(resource_type, dep_config, responses)
            mocks[dep_name] = mock
            logger.info(f"Created mock dependency '{dep_name}' of type '{resource_type}'")

        return mocks
