#!/usr/bin/env python3
"""Test the full transformation."""
import sys
sys.path.insert(0, "/Users/ryan.porter/Projects/Tactus_4")

from tactus.core.runtime import TactusRuntime
from tactus.adapters.memory import MemoryStorage

source = """-- Simplest possible test
print("Starting super simple test")

function main()
    print("IN MAIN FUNCTION!")
    return {test = "success"}
end

print("Defined main function")"""

# Create a minimal runtime just to get the transform method
runtime = TactusRuntime(
    procedure_id="test",
    storage_backend=MemoryStorage(),
)

transformed = runtime._maybe_transform_script_mode_source(source)

print("="*60)
print("TRANSFORMED SOURCE:")
print("="*60)
print(transformed)
print("="*60)
