#!/usr/bin/env python3
"""Test Lua function environment."""

import lupa

lua = lupa.LuaRuntime()

# Define a function in one context
lua.execute("""
function test_func()
    print("TEST FUNC BODY")
    return {result = "success"}
end
""")

# Get the function
test_func = lua.globals()["test_func"]

# Try calling it
print("Calling test_func...")
result = test_func()
print(f"Result: {result}")

# Now try removing print and calling again
print("\nNow testing if print is available...")
lua.execute("""
print("Print is available here")
""")

# Check if function still works
print("\nCalling again...")
result2 = test_func()
print(f"Result 2: {result2}")
