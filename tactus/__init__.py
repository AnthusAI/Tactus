"""
Tactus: Lua-based DSL for agentic workflows.

Tactus provides a declarative workflow engine for AI agents with pluggable
backends for storage, HITL, and chat recording.
"""

__version__ = "0.8.0"

# Core exports
from tactus.core.runtime import TactusRuntime
from tactus.core.exceptions import (
    TactusRuntimeError,
    ProcedureWaitingForHuman,
    ProcedureConfigError,
    LuaSandboxError,
    OutputValidationError,
)

# Protocol exports
from tactus.protocols.storage import StorageBackend, ProcedureMetadata
from tactus.protocols.models import CheckpointEntry
from tactus.protocols.hitl import HITLHandler, HITLRequest, HITLResponse
from tactus.protocols.chat_recorder import ChatRecorder, ChatMessage
from tactus.protocols.config import TactusConfig, ProcedureConfig

__all__ = [
    # Version
    "__version__",
    # Runtime
    "TactusRuntime",
    # Exceptions
    "TactusRuntimeError",
    "ProcedureWaitingForHuman",
    "ProcedureConfigError",
    "LuaSandboxError",
    "OutputValidationError",
    # Protocols
    "StorageBackend",
    "ProcedureMetadata",
    "CheckpointEntry",
    "HITLHandler",
    "HITLRequest",
    "HITLResponse",
    "ChatRecorder",
    "ChatMessage",
    "TactusConfig",
    "ProcedureConfig",
]
