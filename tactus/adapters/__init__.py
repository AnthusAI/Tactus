"""
Tactus adapters - Built-in implementations of Tactus protocols.
"""

from tactus.adapters.memory import MemoryStorage
from tactus.adapters.file_storage import FileStorage

# Legacy HITL handler (maintained for backward compatibility)
from tactus.adapters.cli_hitl import CLIHITLHandler

# New control loop architecture
from tactus.adapters.control_loop import ControlLoopHandler
from tactus.adapters.channels import load_channels_from_config, load_default_channels
from tactus.adapters.channels.cli import CLIControlChannel

__all__ = [
    "MemoryStorage",
    "FileStorage",
    # Legacy HITL
    "CLIHITLHandler",
    # New control loop
    "ControlLoopHandler",
    "CLIControlChannel",
    "load_channels_from_config",
    "load_default_channels",
]
