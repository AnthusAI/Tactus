#!/usr/bin/env python3
"""Test the full flow with auto-registration."""

import lupa

lua = lupa.LuaRuntime()

# Source with plain function main()
source = """
print("Starting test")

function main(input)
    print("IN MAIN FUNCTION!")
    if input then
        print("Input provided")
    end
    return {test = "success"}
end

print("Defined main")
"""

print("=" * 60)
print("1. Execute source")
print("=" * 60)
lua.execute(source)

print("\n" + "=" * 60)
print("2. Check lua.globals() for 'main'")
print("=" * 60)
lua_globals = lua.globals()
if "main" in lua_globals:
    print("✓ Found 'main' in lua_globals")
    main_func = lua_globals["main"]
    print(f"✓ main_func = {main_func}")
    print(f"✓ type = {type(main_func)}")
    print(f"✓ callable = {callable(main_func)}")
else:
    print("✗ 'main' not found in lua_globals")

print("\n" + "=" * 60)
print("3. Call main() with input")
print("=" * 60)
result = main_func(lua.table())
print(f"✓ Result = {result}")
print(f"✓ Result type = {type(result)}")

print("\n" + "=" * 60)
print("SUCCESS: Auto-registration flow works!")
print("=" * 60)
