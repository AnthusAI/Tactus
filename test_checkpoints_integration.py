#!/usr/bin/env python3
"""
Test script to verify checkpoint integration is working.

Run this after starting the backend to verify:
1. ExecutionRuns can be saved
2. API endpoints work
3. Runs can be listed and retrieved
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from tactus.core import TactusRuntime
from tactus.adapters.file_storage import FileStorage


async def test_integration():
    print("=" * 60)
    print("Testing Checkpoint Integration")
    print("=" * 60)

    # Read a simple example
    example_path = Path("examples/01-basics-hello-world.tac")
    if not example_path.exists():
        print(f"❌ Example file not found: {example_path}")
        return False

    source = example_path.read_text()
    print(f"\n✓ Loaded example: {example_path}")

    # Create runtime with FileStorage
    storage = FileStorage()
    runtime = TactusRuntime(
        procedure_id="checkpoint_test",
        storage_backend=storage,
    )
    print("✓ Created runtime with FileStorage")

    # Execute (will fail due to no API key, but that's ok)
    print("\n→ Executing procedure (expected to fail without API key)...")
    try:
        result = await runtime.execute(source, context={}, format="lua")
        success = result.get("success", False)
    except Exception as e:
        print(f"  Expected error: {type(e).__name__}")
        success = False

    # Save ExecutionRun
    if runtime.execution_context:
        status = "COMPLETED" if success else "FAILED"
        run_id = runtime.execution_context.save_execution_run(
            procedure_name="checkpoint_test",
            file_path=str(example_path.absolute()),
            status=status
        )
        print(f"✓ Saved ExecutionRun with ID: {run_id}")

        # Verify it was saved
        try:
            loaded_run = storage.load_run(run_id)
            print(f"✓ Successfully loaded run back from storage")
            print(f"  - Status: {loaded_run.status}")
            print(f"  - Checkpoints: {len(loaded_run.execution_log)}")

            # Test API
            print("\n→ Testing TraceManager API...")
            from tactus.tracing import TraceManager
            trace_mgr = TraceManager(storage)

            runs = trace_mgr.list_runs(limit=10)
            print(f"✓ Found {len(runs)} total runs")

            for i, run in enumerate(runs[-3:], 1):
                print(f"  {i}. {run.procedure_name}: {run.status} ({len(run.execution_log)} checkpoints)")

            print("\n" + "=" * 60)
            print("✓ ALL TESTS PASSED")
            print("=" * 60)
            print("\nNext steps:")
            print("1. Start backend: cd tactus-ide/backend && python app.py")
            print("2. Start frontend: cd tactus-ide/frontend && npm run dev")
            print("3. Run a procedure in the IDE")
            print("4. Check Checkpoints tab - it should auto-refresh and show runs")
            return True

        except Exception as e:
            print(f"❌ Failed to load run: {e}")
            import traceback
            traceback.print_exc()
            return False
    else:
        print("❌ No execution_context - this should not happen!")
        return False


if __name__ == "__main__":
    success = asyncio.run(test_integration())
    sys.exit(0 if success else 1)
