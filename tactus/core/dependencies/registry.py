"""
Resource registry for dependency injection in Tactus procedures.

This module provides the infrastructure for declaring, creating, and managing
external dependencies (HTTP clients, databases, caches) that procedures need.
"""

from enum import Enum
from typing import Dict, Any
import logging

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
    async def create(resource_type: str, config: Dict[str, Any]) -> Any:
        """
        Create a real resource from configuration.

        Args:
            resource_type: Type of resource (http_client, postgres, redis)
            config: Configuration dictionary from procedure DSL

        Returns:
            Configured resource instance

        Raises:
            ValueError: If resource_type is unknown
            ImportError: If required library is not installed
        """
        if resource_type == ResourceType.HTTP_CLIENT.value:
            return await ResourceFactory._create_http_client(config)
        elif resource_type == ResourceType.POSTGRES.value:
            return await ResourceFactory._create_postgres(config)
        elif resource_type == ResourceType.REDIS.value:
            return await ResourceFactory._create_redis(config)
        else:
            raise ValueError(f"Unknown resource type: {resource_type}")

    @staticmethod
    async def _create_http_client(config: Dict[str, Any]) -> Any:
        """Create HTTP client (httpx.AsyncClient)."""
        try:
            import httpx
        except ImportError:
            raise ImportError(
                "httpx is required for HTTP client dependencies. "
                "Install it with: pip install httpx"
            )

        base_url = config.get("base_url")
        headers = config.get("headers", {})
        timeout = config.get("timeout", 30.0)

        logger.info(f"Creating HTTP client for base_url={base_url}")

        return httpx.AsyncClient(base_url=base_url, headers=headers, timeout=timeout)

    @staticmethod
    async def _create_postgres(config: Dict[str, Any]) -> Any:
        """Create PostgreSQL connection pool (asyncpg.Pool)."""
        try:
            import asyncpg
        except ImportError:
            raise ImportError(
                "asyncpg is required for PostgreSQL dependencies. "
                "Install it with: pip install asyncpg"
            )

        connection_string = config["connection_string"]
        pool_size = config.get("pool_size", 10)
        max_pool_size = config.get("max_pool_size", 20)

        logger.info(f"Creating PostgreSQL pool with size={pool_size}")

        return await asyncpg.create_pool(
            connection_string, min_size=pool_size, max_size=max_pool_size
        )

    @staticmethod
    async def _create_redis(config: Dict[str, Any]) -> Any:
        """Create Redis client (redis.asyncio.Redis)."""
        try:
            import redis.asyncio as redis
        except ImportError:
            raise ImportError(
                "redis is required for Redis dependencies. " "Install it with: pip install redis"
            )

        url = config["url"]

        logger.info(f"Creating Redis client for url={url}")

        return redis.from_url(url, encoding="utf-8", decode_responses=True)

    @staticmethod
    async def create_all(dependencies_config: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        """
        Create all dependencies from configuration.

        Args:
            dependencies_config: Dict mapping dependency name to config

        Returns:
            Dict mapping dependency name to created resource
        """
        resources = {}

        for name, config in dependencies_config.items():
            resource_type = config.get("type")
            if not resource_type:
                raise ValueError(f"Dependency '{name}' missing 'type' field")

            logger.info(f"Creating dependency '{name}' of type '{resource_type}'")
            resources[name] = await ResourceFactory.create(resource_type, config)

        return resources


class ResourceManager:
    """
    Manages lifecycle of dependency resources.

    Handles cleanup of HTTP connections, database pools, etc.
    when procedure completes.
    """

    def __init__(self):
        self.resources: Dict[str, Any] = {}

    async def add_resource(self, name: str, resource: Any) -> None:
        """Add a resource to be managed."""
        self.resources[name] = resource
        logger.debug(f"Added resource '{name}' to manager")

    async def cleanup(self) -> None:
        """Clean up all managed resources."""
        logger.info(f"Cleaning up {len(self.resources)} resources")

        for name, resource in self.resources.items():
            try:
                await self._cleanup_resource(name, resource)
            except Exception as e:
                logger.error(f"Error cleaning up resource '{name}': {e}")

    async def _cleanup_resource(self, name: str, resource: Any) -> None:
        """Clean up a single resource based on its type."""
        # HTTP client cleanup
        if hasattr(resource, "aclose"):
            logger.debug(f"Closing HTTP client '{name}'")
            await resource.aclose()

        # PostgreSQL pool cleanup
        elif hasattr(resource, "close") and hasattr(resource, "wait_closed"):
            logger.debug(f"Closing PostgreSQL pool '{name}'")
            await resource.close()
            await resource.wait_closed()

        # Redis client cleanup
        elif hasattr(resource, "close") and not hasattr(resource, "wait_closed"):
            logger.debug(f"Closing Redis client '{name}'")
            await resource.close()

        else:
            logger.warning(f"Unknown resource type for '{name}', no cleanup performed")
