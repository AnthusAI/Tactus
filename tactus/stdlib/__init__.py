"""Tactus Standard Library.

The standard library provides high-level primitives for common AI tasks:

## Primitives (injected into Lua)

### Classify - Smart classification with retry logic
    result = Classify {
        classes = {"Yes", "No"},
        prompt = "Did the agent greet the customer?",
        input = transcript
    }
    -- result.value = "Yes"
    -- result.confidence = 0.92
    -- result.explanation = "The agent said 'Hello'..."

### Coming Soon
- Extract: Schema-based information extraction with validation
- Match: Fuzzy matching verification
- Generate: Constrained generation with validation

## Utility Modules (via require)

The standard library also includes .tac files in the tac/ subdirectory.
These are loaded via Lua's require() function:

    local done = require("tactus.tools.done")
    local log = require("tactus.tools.log")

See tactus/stdlib/tac/ for available modules.
"""

from .classify import ClassifyPrimitive
from .extract import ExtractPrimitive

__all__ = ["ClassifyPrimitive", "ExtractPrimitive"]
