#!/usr/bin/env python3
"""Test Lua function parameter handling."""

import lupa

lua = lupa.LuaRuntime()

# Test 1: Function WITH parameter
print("=== Test 1: Function WITH parameter ===")
lua.execute("""
function with_param(input)
    print("WITH_PARAM: input type = " .. type(input))
    return {test = "with_param"}
end
""")
with_param_func = lua.globals()["with_param"]
result1 = with_param_func(lua.table())
print(f"Result 1: {result1}\n")

# Test 2: Function WITHOUT parameter
print("=== Test 2: Function WITHOUT parameter ===")
lua.execute("""
function no_param()
    print("NO_PARAM: called")
    return {test = "no_param"}
end
""")
no_param_func = lua.globals()["no_param"]
print("Calling no_param with a table argument...")
result2 = no_param_func(lua.table())  # Calling with param even though function expects none
print(f"Result 2: {result2}\n")

# Test 3: Function WITHOUT parameter called without args
print("=== Test 3: Function WITHOUT parameter, no args ===")
result3 = no_param_func()
print(f"Result 3: {result3}")
