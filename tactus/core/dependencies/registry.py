"""
Resource registry for dependency injection in Tactus procedures.

This module provides the infrastructure for declaring, creating, and managing
external dependencies (HTTP clients, databases, caches) that procedures need.
"""

import logging
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class ResourceType(Enum):
    """Supported dependency resource types."""

    HTTP_CLIENT = "http_client"
    POSTGRES = "postgres"
    REDIS = "redis"


class ResourceFactory:
    """
    Factory for creating real dependency resources from configuration.

    This factory creates actual HTTP clients, database connections, etc.
    based on the configuration provided in procedure DSL.
    """

    @staticmethod
    async def create(resource_type: str, resource_config: dict[str, Any]) -> Any:
        """
        Create a real resource from configuration.

        Args:
            resource_type: Type of resource (http_client, postgres, redis)
            resource_config: Configuration dictionary from procedure DSL

        Returns:
            Configured resource instance

        Raises:
            ValueError: If resource_type is unknown
            ImportError: If required library is not installed
        """
        if resource_type == ResourceType.HTTP_CLIENT.value:
            return await ResourceFactory._create_http_client(resource_config)
        if resource_type == ResourceType.POSTGRES.value:
            return await ResourceFactory._create_postgres(resource_config)
        if resource_type == ResourceType.REDIS.value:
            return await ResourceFactory._create_redis(resource_config)
        raise ValueError(f"Unknown resource type: {resource_type}")

    @staticmethod
    async def _create_http_client(resource_config: dict[str, Any]) -> Any:
        """Create HTTP client (httpx.AsyncClient)."""
        try:
            import httpx
        except ImportError:
            raise ImportError(
                "httpx is required for HTTP client dependencies. Install it with: pip install httpx"
            )

        base_url = resource_config.get("base_url")
        headers = resource_config.get("headers", {})
        timeout_seconds = resource_config.get("timeout", 30.0)

        logger.info("Creating HTTP client for base_url=%s", base_url)

        return httpx.AsyncClient(
            base_url=base_url,
            headers=headers,
            timeout=timeout_seconds,
        )

    @staticmethod
    async def _create_postgres(resource_config: dict[str, Any]) -> Any:
        """Create PostgreSQL connection pool (asyncpg.Pool)."""
        try:
            import asyncpg
        except ImportError:
            raise ImportError(
                "asyncpg is required for PostgreSQL dependencies. "
                "Install it with: pip install asyncpg"
            )

        connection_string = resource_config["connection_string"]
        pool_size = resource_config.get("pool_size", 10)
        max_pool_size = resource_config.get("max_pool_size", 20)

        logger.info("Creating PostgreSQL pool with size=%s", pool_size)

        return await asyncpg.create_pool(
            connection_string, min_size=pool_size, max_size=max_pool_size
        )

    @staticmethod
    async def _create_redis(resource_config: dict[str, Any]) -> Any:
        """Create Redis client (redis.asyncio.Redis)."""
        try:
            import redis.asyncio as redis
        except ImportError:
            raise ImportError(
                "redis is required for Redis dependencies. Install it with: pip install redis"
            )

        url = resource_config["url"]

        logger.info("Creating Redis client for url=%s", url)

        return redis.from_url(url, encoding="utf-8", decode_responses=True)

    @staticmethod
    async def create_all(dependencies_config: dict[str, dict[str, Any]]) -> dict[str, Any]:
        """
        Create all dependencies from configuration.

        Args:
            dependencies_config: Dict mapping dependency name to config

        Returns:
            Dict mapping dependency name to created resource
        """
        resources: dict[str, Any] = {}

        for dependency_name, dependency_config in dependencies_config.items():
            resource_type = dependency_config.get("type")
            if not resource_type:
                raise ValueError(f"Dependency '{dependency_name}' missing 'type' field")

            logger.info(
                "Creating dependency '%s' of type '%s'",
                dependency_name,
                resource_type,
            )
            resources[dependency_name] = await ResourceFactory.create(
                resource_type, dependency_config
            )

        return resources


class ResourceManager:
    """
    Manages lifecycle of dependency resources.

    Handles cleanup of HTTP connections, database pools, etc.
    when procedure completes.
    """

    def __init__(self):
        self.resources: dict[str, Any] = {}

    async def add_resource(self, name: str, resource: Any) -> None:
        """Add a resource to be managed."""
        self.resources[name] = resource
        logger.debug("Added resource '%s' to manager", name)

    async def cleanup(self) -> None:
        """Clean up all managed resources."""
        logger.info("Cleaning up %s resources", len(self.resources))

        for resource_name, resource in self.resources.items():
            try:
                await self._cleanup_resource(resource_name, resource)
            except Exception as exception:
                logger.error(
                    "Error cleaning up resource '%s': %s",
                    resource_name,
                    exception,
                )

    async def _cleanup_resource(self, resource_name: str, resource: Any) -> None:
        """Clean up a single resource based on its type."""
        # HTTP client cleanup
        if hasattr(resource, "aclose"):
            logger.debug("Closing HTTP client '%s'", resource_name)
            await resource.aclose()
            return

        # PostgreSQL pool cleanup
        if hasattr(resource, "close") and hasattr(resource, "wait_closed"):
            logger.debug("Closing PostgreSQL pool '%s'", resource_name)
            await resource.close()
            await resource.wait_closed()
            return

        # Redis client cleanup
        if hasattr(resource, "close") and not hasattr(resource, "wait_closed"):
            logger.debug("Closing Redis client '%s'", resource_name)
            await resource.close()
            return

        logger.warning(
            "Unknown resource type for '%s', no cleanup performed",
            resource_name,
        )
