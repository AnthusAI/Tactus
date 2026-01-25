#!/bin/bash
# Test script for Human.inputs() implementation

export PATH="/Users/ryan.porter/Library/Python/3.13/bin:$PATH"

echo "Testing Human.inputs() implementation..."
echo "========================================"
echo ""
echo "This will run the simple test procedure."
echo "You should see a summary of 2 inputs to collect, then prompts for each."
echo ""

# Run with a simple echo input to automatically provide responses
echo -e "Test User\ny" | /Users/ryan.porter/Library/Python/3.13/bin/tactus run examples/92-test-inputs-simple.tac
