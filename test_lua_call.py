#!/usr/bin/env python3
"""Test calling Lua function directly."""

import lupa

lua = lupa.LuaRuntime()

# Execute Lua code that defines a function
print("Executing Lua code to define main...")
lua.execute("""
print("Defining main function...")
function main(input)
    print("IN MAIN BODY! input type: " .. type(input))
    if input then
        print("Input table exists")
    else
        print("Input is nil")
    end
    return {test = "success"}
end
print("Main function defined")
""")

# Get the function
main_func = lua.globals()["main"]
print(f"main_func = {main_func}")
print(f"type = {type(main_func)}")

# Call it with a table
lua_table = lua.table()
print(f"Calling with empty table...")
result = main_func(lua_table)
print(f"Result: {result}")
