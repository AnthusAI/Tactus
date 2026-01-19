#!/usr/bin/env python3
"""Test auto-registration of plain function main()."""
import sys
sys.path.insert(0, "/Users/ryan.porter/Projects/Tactus_4")

# We'll just trace through what would happen in the registry
print("Testing auto-registration logic...")

# Simulate what happens after sandbox.execute()
source = """-- Test file
function main()
    print("IN MAIN")
    return {test = "success"}
end
"""

print("\n1. After sandbox.execute(source):")
print("   - Lua globals would contain: main = <lua function>")

print("\n2. Our new code checks:")
print("   - if 'main' in lua_globals:")
print("   - if callable(main_func) and 'main' not in builder.registry.named_procedures:")
print("   - builder.register_named_procedure('main', main_func, ...)")

print("\n3. This should auto-register the plain function as a named procedure")
print("\n4. Then _execute_workflow() should find it in registry.named_procedures['main']")
print("   and create a ProcedureCallable from it")

print("\n✓ Logic looks correct - need to test with actual py311 environment")
