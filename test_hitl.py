#!/usr/bin/env python3
"""Quick test script to run HITL example and see debug output."""

import sys
from pathlib import Path

# Add project to path
sys.path.insert(0, str(Path(__file__).parent))

from rich.console import Console
from tactus.core.runtime import TactusRuntime
from tactus.adapters.memory import MemoryStorage
from tactus.adapters.cli_hitl import CLIHITLHandler

# Setup
console = Console()
storage = MemoryStorage()
hitl_handler = CLIHITLHandler(console=console)

print(f"[SETUP] Created HITL handler: {hitl_handler}")
print(f"[SETUP] Handler type: {type(hitl_handler)}")

# Create runtime
runtime = TactusRuntime(
    procedure_id="test-hitl",
    storage_backend=storage,
    hitl_handler=hitl_handler,
    source_file_path="examples/90-hitl-debug.tac",
)

print(f"[SETUP] Runtime created")
print(f"[SETUP] Runtime hitl_handler: {runtime.hitl_handler}")

# Load and run
example_path = Path("examples/90-hitl-debug.tac")
source = example_path.read_text()

print(f"\n[RUNNING] Executing procedure...")
result = runtime.execute_lua_code(source, input_data={})

print(f"\n[RESULT] {result}")
