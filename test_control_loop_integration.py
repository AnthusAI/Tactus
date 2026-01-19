#!/usr/bin/env python3
"""Test that ControlLoopHandler is being used."""

import sys
sys.path.insert(0, "/Users/ryan.porter/Projects/Tactus_4")

from tactus.core.runtime import TactusRuntime
from tactus.adapters.memory import MemoryStorage

# Create runtime with default HITL handler
runtime = TactusRuntime(
    procedure_id="test",
    storage_backend=MemoryStorage(),
)

print("=" * 60)
print("HITL Handler Type Check")
print("=" * 60)

if runtime.hitl_handler is None:
    print("✗ No HITL handler configured")
else:
    print(f"✓ HITL handler: {type(runtime.hitl_handler).__name__}")
    print(f"   Module: {type(runtime.hitl_handler).__module__}")

    # Check if it's the new adapter
    from tactus.adapters.control_loop import ControlLoopHITLAdapter
    if isinstance(runtime.hitl_handler, ControlLoopHITLAdapter):
        print("✓ Using new ControlLoopHITLAdapter")
        print(f"   Wrapped handler: {type(runtime.hitl_handler.control_handler).__name__}")
        print(f"   Number of channels: {len(runtime.hitl_handler.control_handler.channels)}")

        for channel in runtime.hitl_handler.control_handler.channels:
            print(f"   - Channel: {channel.channel_id} ({type(channel).__name__})")
    else:
        print("✗ Using old HITLHandler")

print("=" * 60)
