#!/usr/bin/env python3
"""Test control loop with manually loaded channels."""

import sys
sys.path.insert(0, "/Users/ryan.porter/Projects/Tactus_4")

from tactus.core.runtime import TactusRuntime
from tactus.adapters.memory import MemoryStorage
from tactus.adapters.channels.cli import CLIControlChannel
from tactus.adapters.control_loop import ControlLoopHandler, ControlLoopHITLAdapter

# Manually create control loop handler with CLI channel
channels = [CLIControlChannel()]
control_handler = ControlLoopHandler(channels=channels, storage=MemoryStorage())
hitl_handler = ControlLoopHITLAdapter(control_handler)

# Create runtime with this handler
runtime = TactusRuntime(
    procedure_id="test",
    storage_backend=MemoryStorage(),
    hitl_handler=hitl_handler,
)

print("=" * 60)
print("Manual Control Loop Setup")
print("=" * 60)
print(f"✓ HITL handler: {type(runtime.hitl_handler).__name__}")
print(f"✓ Control handler: {type(hitl_handler.control_handler).__name__}")
print(f"✓ Channels: {len(hitl_handler.control_handler.channels)}")
for ch in hitl_handler.control_handler.channels:
    print(f"   - {ch.channel_id}")
print("=" * 60)
