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
    MessageClassification,
)

# Control loop protocol and models
from tactus.protocols.control import (
    ControlChannel,
    ControlRequest,
    ControlResponse,
    ControlRequestType,
    ControlOption,
    ControlInteraction,
    ConversationMessage,
    ChannelCapabilities,
    DeliveryResult,
    ControlLoopConfig,
)

# Protocols
from tactus.protocols.storage import StorageBackend
from tactus.protocols.hitl import HITLHandler
from tactus.protocols.chat_recorder import ChatRecorder
from tactus.protocols.model_attempt import (
    ModelAttemptAuthority,
    ModelAttemptOutcome,
    ModelAttemptPlan,
    ModelAttemptReplayPayload,
    ModelAttemptReservation,
    ModelAttemptUsage,
)

# Configuration
from tactus.protocols.config import TactusConfig, ProcedureConfig

__all__ = [
    # Models
    "CheckpointEntry",
    "ProcedureMetadata",
    "HITLRequest",
    "HITLResponse",
    "ChatMessage",
    "MessageClassification",
    # Control loop
    "ControlChannel",
    "ControlRequest",
    "ControlResponse",
    "ControlRequestType",
    "ControlOption",
    "ControlInteraction",
    "ConversationMessage",
    "ChannelCapabilities",
    "DeliveryResult",
    "ControlLoopConfig",
    # Protocols
    "StorageBackend",
    "HITLHandler",
    "ChatRecorder",
    "ModelAttemptAuthority",
    "ModelAttemptOutcome",
    "ModelAttemptPlan",
    "ModelAttemptReplayPayload",
    "ModelAttemptReservation",
    "ModelAttemptUsage",
    # Config
    "TactusConfig",
    "ProcedureConfig",
]
