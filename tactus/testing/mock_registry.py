"""
Unified mock registry for managing all mocks (dependencies + HITL).

This provides a central place to configure mocks for both dependencies
and HITL interactions, usable in BDD tests and evaluations.
"""

import logging
from typing import Dict, Any, Optional
from tactus.testing.mock_dependencies import MockHTTPClient, MockDatabase, MockRedis
from tactus.testing.mock_hitl import MockHITLHandler

logger = logging.getLogger(__name__)


class UnifiedMockRegistry:
    """
    Central registry for all mocks (dependencies + HITL).

    This allows test scenarios to configure mock responses via
    Gherkin steps or programmatically.
    """

    def __init__(self, hitl_handler: Optional[MockHITLHandler] = None):
        """
        Initialize unified mock registry.

        Args:
            hitl_handler: Optional existing HITL handler to use
        """
        # HTTP dependency mocks (dep_name -> MockHTTPClient)
        self.http_mocks: Dict[str, MockHTTPClient] = {}

        # Database mocks
        self.db_mocks: Dict[str, MockDatabase] = {}

        # Redis mocks
        self.redis_mocks: Dict[str, MockRedis] = {}

        # HITL mock handler
        self.hitl_mock: MockHITLHandler = hitl_handler or MockHITLHandler()

        # Store all created mocks for cleanup
        self.all_mocks: Dict[str, Any] = {}

    def configure_http_response(
        self, dep_name: str, path: Optional[str], response: str, status_code: int = 200
    ) -> None:
        """
        Configure mock HTTP response via Gherkin step.

        Args:
            dep_name: Name of the HTTP dependency
            path: URL path (or None for default response)
            response: Response text (usually JSON string)
            status_code: HTTP status code

        Example:
            registry.configure_http_response("weather_api", "/data", '{"temp": 72}')
        """
        if dep_name not in self.http_mocks:
            self.http_mocks[dep_name] = MockHTTPClient()

        if path:
            self.http_mocks[dep_name].add_response(path, response, status_code)
        else:
            # Set default response for any path
            self.http_mocks[dep_name].responses["_default"] = {
                "text": response,
                "status_code": status_code,
            }

        logger.debug(f"Configured mock HTTP response for {dep_name}: {path} -> {response[:50]}...")

    def configure_hitl_response(self, interaction_type: str, value: Any) -> None:
        """
        Configure HITL mock response via Gherkin step.

        Args:
            interaction_type: Type of interaction (approval, input, review)
            value: The value to return

        Example:
            registry.configure_hitl_response("approval", True)
        """
        self.hitl_mock.configure_response(interaction_type, value)

    def configure_hitl_message_response(self, message_prefix: str, value: Any) -> None:
        """
        Configure HITL mock response for specific message.

        Args:
            message_prefix: Prefix of the message to match
            value: The value to return

        Example:
            registry.configure_hitl_message_response("Approve payment", False)
        """
        self.hitl_mock.configure_message_response(message_prefix, value)

    async def create_mock_dependencies(
        self, dependencies_config: Dict[str, Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Create mock dependencies for runtime.

        This is called by the test runner to create mocks based on
        the procedure's dependency declarations.

        Args:
            dependencies_config: Dict mapping dependency name to config

        Returns:
            Dict mapping dependency name to mock resource
        """
        mocks = {}

        for dep_name, dep_config in dependencies_config.items():
            resource_type = dep_config.get("type")

            if resource_type == "http_client":
                # Use pre-configured mock if it exists, otherwise create new one
                if dep_name in self.http_mocks:
                    mock = self.http_mocks[dep_name]
                else:
                    mock = MockHTTPClient()
                    self.http_mocks[dep_name] = mock

                mock.base_url = dep_config.get("base_url")
                mocks[dep_name] = mock

            elif resource_type == "postgres":
                if dep_name not in self.db_mocks:
                    self.db_mocks[dep_name] = MockDatabase()
                mocks[dep_name] = self.db_mocks[dep_name]

            elif resource_type == "redis":
                if dep_name not in self.redis_mocks:
                    self.redis_mocks[dep_name] = MockRedis()
                mocks[dep_name] = self.redis_mocks[dep_name]

            else:
                logger.warning(
                    f"Unknown resource type '{resource_type}' for dependency '{dep_name}'"
                )
                continue

            self.all_mocks[dep_name] = mocks[dep_name]
            logger.info(f"Created mock dependency '{dep_name}' of type '{resource_type}'")

        return mocks

    def get_hitl_handler(self) -> MockHITLHandler:
        """Get the HITL mock handler."""
        return self.hitl_mock

    def clear_all(self) -> None:
        """Clear all mock configurations and history."""
        self.http_mocks.clear()
        self.db_mocks.clear()
        self.redis_mocks.clear()
        self.hitl_mock.clear_history()
        self.all_mocks.clear()
        logger.debug("Cleared all mocks")

    def get_mock(self, dep_name: str) -> Optional[Any]:
        """Get a specific mock by name."""
        return self.all_mocks.get(dep_name)
