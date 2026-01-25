#!/usr/bin/env python3.13
"""
Direct test of inputs() method to find the error.
"""

# Mock execution context
class MockExecutionContext:
    def wait_for_human(self, **kwargs):
        print(f"wait_for_human called with: {kwargs.keys()}")
        print(f"  request_type: {kwargs.get('request_type')}")
        print(f"  metadata type: {type(kwargs.get('metadata'))}")
        print(f"  metadata: {kwargs.get('metadata')}")

        class MockResponse:
            value = {"name": "Test", "confirmed": True}
        return MockResponse()

    def checkpoint(self, fn, name):
        print(f"checkpoint called: {name}")
        return fn()

# Create Human primitive
from tactus.primitives.human import HumanPrimitive

ctx = MockExecutionContext()
human = HumanPrimitive(ctx, {})

# Test the inputs method
print("Testing Human.inputs()")
try:
    items = [
        {
            "id": "name",
            "label": "Name",
            "type": "input",
            "message": "What is your name?",
            "metadata": {"placeholder": "Enter your name"}
        },
        {
            "id": "confirmed",
            "label": "Confirm",
            "type": "approval",
            "message": "Is this correct?"
        }
    ]

    result = human.inputs(items)
    print(f"Success! Result: {result}")
except Exception as e:
    print(f"Error: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
