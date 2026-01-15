"""
Tactus primitives - Lua-callable Python objects.

These primitives are injected into the Lua sandbox and provide
the core functionality for workflow execution.
"""

from tactus.primitives.state import StatePrimitive
from tactus.primitives.control import IterationsPrimitive, StopPrimitive
from tactus.primitives.tool import ToolPrimitive
from tactus.primitives.log import LogPrimitive
from tactus.primitives.step import StepPrimitive, CheckpointPrimitive
from tactus.primitives.json import JsonPrimitive
from tactus.primitives.retry import RetryPrimitive
from tactus.primitives.file import FilePrimitive

from tactus.primitives.human import HumanPrimitive
from tactus.primitives.system import SystemPrimitive
from tactus.primitives.host import HostPrimitive

# MessageHistory primitive is now available
from tactus.primitives.message_history import MessageHistoryPrimitive

# NOTE: AgentPrimitive and ResultPrimitive have been replaced by DSPy implementation
# Agent functionality is now provided by tactus.dspy.agent

# These will be imported when their dependencies are ready
# from tactus.primitives.system import SystemPrimitive
# from tactus.primitives.procedure import ProcedurePrimitive
# from tactus.primitives.graph import GraphNodePrimitive

__all__ = [
    "StatePrimitive",
    "IterationsPrimitive",
    "StopPrimitive",
    "ToolPrimitive",
    "HumanPrimitive",
    "LogPrimitive",
    "StepPrimitive",
    "CheckpointPrimitive",
    "MessageHistoryPrimitive",
    "JsonPrimitive",
    "RetryPrimitive",
    "FilePrimitive",
    "SystemPrimitive",
    "HostPrimitive",
    # "AgentPrimitive",  # Replaced by DSPy implementation
    # "ResultPrimitive",  # Replaced by DSPy implementation
]
