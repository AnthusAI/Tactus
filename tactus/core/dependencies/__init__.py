"""
Dependency injection infrastructure for Tactus procedures.

This package provides the infrastructure for declaring, creating, and managing
external dependencies like HTTP clients, databases, and caches.
"""

from .registry import ResourceType, ResourceFactory, ResourceManager

__all__ = [
    "ResourceType",
    "ResourceFactory",
    "ResourceManager",
]
