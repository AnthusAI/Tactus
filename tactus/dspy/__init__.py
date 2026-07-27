"""
Tactus DSPy Integration

This module provides the integration layer between Tactus and DSPy,
exposing DSPy primitives as first-class Tactus language constructs.

The integration follows a layered approach:
- Low-level primitives (Module, Signature, etc.) are thin wrappers over DSPy
- High-level constructs (Agent) are built in Tactus using these primitives
"""

import os

# Allow disabling DSPy's disk cache (16-shard SQLite FanoutCache) to avoid
# lock contention when running multiple evaluations in parallel.
# DSPy creates its FanoutCache at import time (before this code runs), so we
# must also close the already-opened cache to release its file descriptors.
if os.environ.get("DSPY_DISABLE_DISK_CACHE", "").lower() in ("1", "true", "yes"):
    import dspy

    _old_cache = getattr(dspy, "cache", None)
    if _old_cache is not None:
        _old_disk = getattr(_old_cache, "disk_cache", None)
        if _old_disk is not None and hasattr(_old_disk, "close"):
            try:
                _old_disk.close()
            except Exception:
                # Best-effort cleanup: ignore close failures so cache disabling
                # does not prevent module import or configuration.
                pass
    from dspy.clients import configure_cache

    configure_cache(enable_disk_cache=False)

from tactus.dspy.agent import DSPyAgentHandle, create_dspy_agent, prewarm_agent_runtime
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
    "prewarm_agent_runtime",
]
