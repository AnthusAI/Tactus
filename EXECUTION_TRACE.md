# Execution Trace: Plain Function main() Support

## Test File: examples/90-super-simple.tac

```lua
print("Starting test")

function main()
    print("IN MAIN FUNCTION!")
    return {test = "success"}
end

print("Defined main")
```

## Execution Trace

### Step 1: TactusRuntime.__init__()
- Creates runtime instance
- Initializes storage, config, execution context
- Sets up primitives (Human, Tool, etc.)

### Step 2: TactusRuntime.run()
- Calls `self.initialize()`
- Calls `await self.execute()`

### Step 3: TactusRuntime.initialize()
- Calls `self._parse_declarations(source_code)`

### Step 4: _maybe_transform_script_mode_source()
**Before fix:** Would detect `return` inside function and wrap everything
**After fix:**
```python
# Line 2453: Check for named function definitions
if re.search(r"(?m)^\s*(?:local\s+)?function\s+[A-Za-z_][A-Za-z0-9_]*\s*\(", source):
    return source  # ✅ EARLY RETURN - Don't transform!
```

Result: Source returned unchanged, no wrapping

### Step 5: _parse_declarations() - Execute Source
```python
# Line 2748: Execute the file
execution_result = sandbox.execute(source)
```

**Lua execution:**
```
Starting test          ← Top-level print
Defined main           ← Top-level print
```

**Lua state after execution:**
```lua
lua.globals() = {
    print = <function>,
    main = <function>,      ← Our function!
    Human = <table>,
    Tool = <table>,
    ...
}
```

### Step 6: Auto-Register main() - NEW CODE
```python
# Lines 2769-2781: Check lua.globals() for main
lua_globals = sandbox.lua.globals()
if "main" in lua_globals:                          # ✅ TRUE
    main_func = lua_globals["main"]                # ✅ Get function
    if callable(main_func):                        # ✅ TRUE
        if "main" not in builder.registry.named_procedures:  # ✅ TRUE
            logger.info("[AUTO_REGISTER] Found plain function main()...")
            builder.register_named_procedure(
                name="main",
                lua_function=main_func,            # ✅ Register it!
                input_schema={},
                output_schema={},
                state_schema={},
            )
```

**Registry state after auto-registration:**
```python
registry.named_procedures = {
    "main": {
        "function": <lua function>,
        "input_schema": {},
        "output_schema": {},
        "state_schema": {},
    }
}
```

### Step 7: Return from initialize()
- Registry contains "main" procedure
- Runtime is ready to execute

### Step 8: TactusRuntime.execute()
- Calls `self._execute_workflow()`

### Step 9: _execute_workflow()
```python
# Line 2338: Check for named procedures
if self.registry:
    if "main" in self.registry.named_procedures:   # ✅ TRUE (registered in Step 6)
        logger.info("Executing named 'main' procedure")
        main_proc = self.registry.named_procedures["main"]

        # Line 2352: Create callable wrapper
        from tactus.primitives.procedure_callable import ProcedureCallable
        main_callable = ProcedureCallable(
            name="main",
            procedure_function=main_proc["function"],  # ✅ Our Lua function
            input_schema=main_proc["input_schema"],
            output_schema=main_proc["output_schema"],
            state_schema=main_proc["state_schema"],
            execution_context=self.execution_context,
            lua_sandbox=self.lua_sandbox,
            is_main=True,
        )

        # Gather input parameters (empty in this case)
        input_params = {}

        # Line 2385: Execute!
        print(f"About to call main_callable")
        workflow_result = main_callable(input_params)
```

### Step 10: ProcedureCallable.__call__()
```python
# tactus/primitives/procedure_callable.py
def __call__(self, input_args=None):
    # Prepare input table
    lua_input = self.lua_sandbox.lua.table()

    # Call the Lua function
    result = self.procedure_function(lua_input)  # ✅ Call main()!

    return result
```

**Lua execution inside main():**
```lua
function main(input)
    print("IN MAIN FUNCTION!")     ← ✅ EXECUTES NOW!
    return {test = "success"}
end
```

**Console output:**
```
IN MAIN FUNCTION!
```

### Step 11: Return Result
- main() returns `{test = "success"}`
- ProcedureCallable converts to Python dict
- Runtime returns result
- Workflow completes successfully

## Complete Output Trace

### Before Fix
```
Starting test
Defined main
✗ Completed with 0 iterations, 0 tools used
```

### After Fix
```
Starting test
Defined main
IN MAIN FUNCTION!               ← ✅ Function body executed!
✓ Workflow completed successfully
```

## Key Changes Summary

| Component | Before | After |
|-----------|--------|-------|
| Script mode transform | Wrapped `function main()` incorrectly | Skips files with named functions |
| Named procedure registration | Only via `Procedure` DSL | Also auto-registers plain `function main()` |
| Execution | Function defined but never called | Function registered and called |
| HITL calls | Never reached (function didn't run) | Work correctly (function runs) |

## Verification

The fix enables both syntax styles:

### Style 1: DSL (Already Worked)
```lua
Procedure {
    function(input)
        local approved = Human.approve({message = "Continue?"})
        return {result = "done"}
    end
}
```
✅ Self-registers via DSL stub

### Style 2: Plain Lua (Now Fixed)
```lua
function main()
    local approved = Human.approve({message = "Continue?"})
    return {result = "done"}
end
```
✅ Auto-registered after execution
✅ Executed by `_execute_workflow()`
✅ HITL calls work correctly
