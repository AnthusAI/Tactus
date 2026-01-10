"""
Tactus protocols and models.

This module exports all Pydantic models and protocol definitions for Tactus.
"""

# Core models
from tactus.protocols.models import (
    CheckpointEntry,
    ProcedureMetadata,
    HITLRequest,
    HITLResponse,
    ChatMessage,
)

# Shared usage/cost + standard result
from tactus.protocols.cost import UsageStats, CostStats
from tactus.protocols.result import TactusResult

# Protocols
from tactus.protocols.storage import StorageBackend
from tactus.protocols.hitl import HITLHandler
from tactus.protocols.chat_recorder import ChatRecorder

# Configuration
from tactus.protocols.config import TactusConfig, ProcedureConfig

__all__ = [
    # Models
    "CheckpointEntry",
    "ProcedureMetadata",
    "HITLRequest",
    "HITLResponse",
    "ChatMessage",
    "UsageStats",
    "CostStats",
    "TactusResult",
    # Protocols
    "StorageBackend",
    "HITLHandler",
    "ChatRecorder",
    # Config
    "TactusConfig",
    "ProcedureConfig",
]
