"""
Tactus DSPy Integration

This module provides the integration layer between Tactus and DSPy,
exposing DSPy primitives as first-class Tactus language constructs.

The integration follows a layered approach:
- Low-level primitives (Module, Signature, etc.) are thin wrappers over DSPy
- High-level constructs (Agent) are built in Tactus using these primitives
"""

from tactus.dspy.agent import DSPyAgentHandle, create_dspy_agent
from tactus.dspy.config import configure_lm, get_current_lm, reset_lm_configuration
from tactus.dspy.history import TactusHistory, create_history
from tactus.dspy.module import TactusModule, create_module
from tactus.dspy.prediction import TactusPrediction, create_prediction, wrap_prediction
from tactus.dspy.signature import (
    create_signature,
    create_structured_signature,
    parse_signature_string,
)

__all__ = [
    "configure_lm",
    "get_current_lm",
    "reset_lm_configuration",
    "create_signature",
    "create_structured_signature",
    "parse_signature_string",
    "TactusModule",
    "create_module",
    "TactusHistory",
    "create_history",
    "TactusPrediction",
    "create_prediction",
    "wrap_prediction",
    "DSPyAgentHandle",
    "create_dspy_agent",
]
