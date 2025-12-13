# Tactus Implementation Guide

This document maps the [SPECIFICATION.md](SPECIFICATION.md) to the actual codebase implementation. It describes where each feature is implemented, what's complete, and what's missing.

**Purpose**: After reading the specification, use this document to understand how features are actually implemented in the code and to identify gaps between the spec and current implementation.

---

## Core Architecture

### TactusRuntime (`tactus/core/runtime.py`)

The main execution engine orchestrating all components.

**Responsibilities:**
- Parses YAML configuration via `ProcedureYAMLParser`
- Initializes Lua sandbox (`LuaSandbox`)
- Creates and injects primitives into Lua environment
- Sets up agents with LLM integration (Pydantic AI)
- Executes procedure Lua code
- Validates output against schema

**Key Methods:**
- `execute(yaml_config, context)` - Main entry point for procedure execution
- `_setup_agents()` - Configures LLM agents with tools from MCP server
- `_inject_primitives()` - Injects all primitives (State, Tool, Human, etc.) into Lua

**Status**: ✅ **Fully Implemented**

### ExecutionContext (`tactus/core/execution_context.py`)

Abstraction layer for checkpointing and HITL operations.

**Components:**
- `BaseExecutionContext` - Base implementation using pluggable storage and HITL handlers
- `InMemoryExecutionContext` - Simple in-memory variant

**Key Methods:**
- `step_run(name, fn)` - Execute function with checkpoint replay
- `wait_for_human(...)` - Suspend execution until human responds
- `checkpoint_*` methods - Checkpoint management

**Status**: ✅ **Fully Implemented** (Local execution context)

**Note**: Lambda Durable Execution Context mentioned in spec is **not implemented**. Only local context exists.

### LuaSandbox (`tactus/core/lua_sandbox.py`)

Safe, restricted Lua execution environment using `lupa`.

**Features:**
- Removes dangerous modules (io, os, debug, package, require)
- Provides safe subset of standard library
- Supports primitive injection
- Attribute filtering for security

**Key Methods:**
- `execute(lua_code)` - Execute Lua procedure code
- `inject_primitive(name, obj)` - Inject Python objects as Lua globals
- `set_global(name, value)` - Set Lua global variables

**Status**: ✅ **Fully Implemented**

---

## DSL Component Implementation

### Document Structure & YAML Parsing

#### YAML Parser (`tactus/core/yaml_parser.py`)

Parses and validates procedure YAML configurations.

**Validates:**
- Required fields: `name`, `version`, `procedure`
- Parameters schema (`params`)
- Outputs schema (`outputs`)
- Agents definitions
- Procedure Lua code (basic syntax check)

**Status**: ✅ **Partially Implemented**

**Missing Validations:**
- ❌ `guards` section (not parsed or validated)
- ❌ `dependencies` section (not parsed or validated)
- ❌ `hitl` declarative configuration (parsed but not validated)
- ❌ `procedures` inline definitions (not parsed)
- ❌ `stages` declarations (not validated)
- ❌ `async`, `max_depth`, `max_turns`, `checkpoint_interval` (not parsed)
- ❌ `return_prompt`, `error_prompt`, `status_prompt` (not parsed)

### Parameters

#### Implementation: DSL Stubs + Registry

**Lua DSL Format (.tac files):**

Parameters are now defined inside the `procedure()` config table:

```lua
procedure({
    params = {
        task = {
            type = "string",
            required = true
        }
    }
}, function()
    local task = params.task
    -- ...
end)
```

**How it works:**
1. The `procedure()` stub in `dsl_stubs.py` accepts two arguments: config table and function
2. When config contains `params`, each parameter is registered via `builder.register_parameter()`
3. Runtime converts registry to config dict format for compatibility
4. Parameters injected into Lua sandbox with default values
5. Context values override defaults
6. Parameters accessible in Lua as `params.param_name`

**Location**: 
- DSL Stub: `tactus/core/dsl_stubs.py` (updated `_procedure` function)
- Registry: `tactus/core/registry.py` (`RegistryBuilder.register_parameter()`)
- Injection: `tactus/core/runtime.py` (`_inject_primitives()`)

**Template Support**: ✅ Parameters accessible in templates via `{params.name}`

**Status**: ✅ **Fully Implemented**

### Outputs

#### Implementation: DSL Stubs + Registry + OutputValidator

**Lua DSL Format (.tac files):**

Outputs are now defined inside the `procedure()` config table:

```lua
procedure({
    outputs = {
        result = {
            type = "string",
            required = true
        }
    }
}, function()
    return {
        result = "completed"
    }
end)
```

**How it works:**
1. The `procedure()` stub in `dsl_stubs.py` accepts two arguments: config table and function
2. When config contains `outputs`, each output is registered via `builder.register_output()`
3. Runtime converts registry to config dict format for compatibility
4. `OutputValidator` created during runtime initialization
5. After workflow execution, `validate()` called on return value
6. Validates required fields, types, and structure
7. Strips undeclared fields if schema present

**Location**: 
- DSL Stub: `tactus/core/dsl_stubs.py` (updated `_procedure` function)
- Registry: `tactus/core/registry.py` (`RegistryBuilder.register_output()`)
- Validator: `tactus/core/output_validator.py`

**Features:**
- Type checking (string, number, boolean, object, array)
- Required field validation
- Lua table conversion to Python dicts
- Clear error messages

**Status**: ✅ **Fully Implemented**

### Summarization Prompts

**Specification Sections:**
- `return_prompt:` - Injected when procedure completes successfully
- `error_prompt:` - Injected when procedure fails
- `status_prompt:` - Injected for async status updates

**Status**: ❌ **Not Implemented**

These prompts are not parsed, stored, or used anywhere in the codebase. Procedures complete normally without final summary turns.

### Async and Recursion Settings

**Specification Settings:**
- `async: true` - Enable async invocation
- `max_depth: 5` - Maximum recursion depth
- `max_turns: 50` - Maximum turns per procedure
- `checkpoint_interval: 10` - Checkpoint interval for recovery

**Status**: ❌ **Not Implemented**

These settings are not parsed or enforced. There's no recursion depth tracking, and no async procedure invocation.

### Execution Contexts

**Specification**: Describes Local Execution Context and Lambda Durable Execution Context.

**Current Implementation:**
- ✅ **Local Execution Context**: Implemented via `BaseExecutionContext`
  - Uses pluggable `StorageBackend` for checkpoints
  - Uses pluggable `HITLHandler` for human interactions
  - Checkpoints stored in procedure metadata
  
- ❌ **Lambda Durable Execution Context**: Not implemented
  - No AWS Lambda Durable Functions SDK integration
  - No `context.create_callback()` support
  - No automatic suspend/resume via Lambda callbacks

**Status**: ✅ **Partially Implemented** (Local only)

### Guards

**Specification**: Validation that runs before procedure executes.

```yaml
guards:
  - |
    if not File.exists(params.file_path) then
      return false, "File not found"
    end
    return true
```

**Status**: ❌ **Not Implemented**

Guards are not parsed by `ProcedureYAMLParser` and are never executed.

### Dependencies

**Specification**: Validates required tools and procedures before execution.

```yaml
dependencies:
  tools:
    - web_search
    - read_document
  procedures:
    - researcher
```

**Status**: ❌ **Not Implemented**

Dependencies are not parsed or validated. Tools are checked at runtime when agents try to use them, but no upfront validation.

### Template Variable Namespaces

**Specification**: `params`, `outputs`, `context`, `state`, `prepared`, `env`

**Current Implementation:**
- ✅ `params` - Fully supported
- ✅ `state` - Fully supported (via `StatePrimitive`)
- ❌ `outputs` - Not available (only in return_prompt, which isn't implemented)
- ❌ `context` - Not implemented
- ❌ `prepared` - Not implemented (agent `prepare` hook not implemented)
- ❌ `env` - Not implemented

**Status**: ✅ **Partially Implemented** (params, state only)

### Human-in-the-Loop (HITL)

#### HumanPrimitive (`tactus/primitives/human.py`)

**Status**: ✅ **Fully Implemented**

All blocking primitives:
- ✅ `Human.approve(opts)` - Request yes/no approval
- ✅ `Human.input(opts)` - Request free-form input
- ✅ `Human.review(opts)` - Request review with options
- ✅ `Human.notify(opts)` - Send non-blocking notification (logs only)
- ✅ `Human.escalate(opts)` - Escalate to human (blocks indefinitely)

**Implementation Details:**
- Uses `ExecutionContext.wait_for_human()` which delegates to `HITLHandler`
- Supports declarative HITL config via `hitl:` YAML section
- Converts Lua tables to Python dicts automatically
- Raises `ProcedureWaitingForHuman` exception to suspend execution

#### HITLHandler Protocol (`tactus/protocols/hitl.py`)

Defines interface for HITL implementations.

**Current Implementations:**
- ✅ `CLIHITLHandler` (`tactus/adapters/cli_hitl.py`) - CLI-based human interaction

#### System.alert()

**Specification**: Programmatic alerts from anywhere (not just procedures).

**Status**: ❌ **Not Implemented**

Only `Human.notify()` exists, which logs notifications. No `System.alert()` primitive or system-level alert infrastructure.

#### Message Classification

**Specification**: `humanInteraction` field values (INTERNAL, CHAT, PENDING_APPROVAL, etc.)

**Status**: ❌ **Not Implemented**

The spec describes message classification, but the current implementation doesn't track `humanInteraction` types. HITL requests are handled but not classified into these categories.

### Inline Procedure Definitions

**Specification**: Procedures can be defined inline in YAML `procedures:` section.

**Status**: ❌ **Not Implemented**

Inline procedures are not parsed by `ProcedureYAMLParser` and cannot be invoked.

### Agent Definitions

#### AgentPrimitive (`tactus/primitives/agent.py`)

**Status**: ✅ **Fully Implemented**

**Features:**
- ✅ LLM integration via Pydantic AI
- ✅ System prompt with template variables (`{params.*}`, `{state.*}`)
- ✅ Initial message support
- ✅ Tool integration (via MCP server)
- ✅ Conversation history tracking
- ✅ Structured output support (Pydantic models)

**Configuration:**
- ✅ `system_prompt` - Template-based system prompt
- ✅ `initial_message` - First message to agent
- ✅ `tools` - List of available tools
- ✅ `model` - LLM model specification
- ✅ `output_schema` - Structured output schema (per agent)
- ✅ `max_turns` - Maximum agent turns (configured but not enforced)

**Missing Features:**
- ❌ `prepare` hook - Not implemented (no `prepared` namespace in templates)
- ❌ `filter` - Not implemented (no ComposedFilter, TokenBudget, etc.)
- ❌ `response.retries` / `response.retry_delay` - Not implemented

**Usage in Lua**: `Worker.turn()` (capitalized agent name)

### Invoking Procedures

**Specification Primitives:**
- `Procedure.run(name, params)` - Synchronous invocation
- `Procedure.spawn(name, params)` - Async invocation
- `Procedure.status(handle)` - Get status
- `Procedure.wait(handle)` - Wait for completion
- `Procedure.inject(handle, message)` - Send guidance
- `Procedure.cancel(handle)` - Abort
- `Procedure.wait_any(handles)` - Wait for first
- `Procedure.wait_all(handles)` - Wait for all

**Status**: ❌ **Not Implemented**

No `Procedure` primitive exists. Procedures cannot invoke other procedures. This blocks:
- Recursive procedure calls
- Async procedure spawning
- Procedure composition

### Stages

#### StagePrimitive (`tactus/primitives/stage.py`)

**Status**: ✅ **Fully Implemented**

**Features:**
- ✅ `Stage.set(name)` - Set current stage
- ✅ `Stage.current()` - Get current stage
- ✅ `Stage.advance()` - Move to next stage in sequence
- ✅ `Stage.is(name)` - Check if in specific stage (mapped from Lua `is` keyword)
- ✅ `Stage.history()` - Get transition history

**Implementation:**
- Validates stage names against `stages:` declaration in YAML
- Tracks stage transitions with timestamps
- Returns history as Lua table

### Exception Handling

**Specification**: Supports `pcall()` for protected calls.

**Status**: ✅ **Fully Implemented**

Lua `pcall()` is available in sandbox (standard Lua feature). No special exception handling beyond standard Lua.

### Primitives Reference

#### Procedure Primitives

**Status**: ❌ **Not Implemented**

All procedure invocation primitives are missing.

#### Step Primitives

#### StepPrimitive (`tactus/primitives/step.py`)

**Status**: ✅ **Fully Implemented**

- ✅ `Step.run(name, fn)` - Execute with checkpointing

**Implementation:**
- Delegates to `ExecutionContext.step_run()`
- On first execution: runs function and caches result
- On replay: returns cached result immediately

#### CheckpointPrimitive (`tactus/primitives/step.py`)

**Status**: ✅ **Fully Implemented**

- ✅ `Checkpoint.clear_all()` - Clear all checkpoints
- ✅ `Checkpoint.clear_after(name)` - Clear from checkpoint onwards
- ✅ `Checkpoint.exists(name)` - Check if exists
- ✅ `Checkpoint.get(name)` - Get cached value

**Usage**: Testing and debugging checkpoint replay behavior.

#### Human Interaction Primitives

**Status**: ✅ **Fully Implemented** (see HITL section above)

#### Agent Primitives

**Status**: ✅ **Fully Implemented**

- ✅ `AgentName.turn()` - Execute agent turn
- ✅ `AgentName.turn({inject = "..."})` - Turn with injected message (not implemented)

**Note**: `turn({inject})` signature not implemented. Only `turn()` without args works.

**Response Access:**
- Response content accessible via `response.content` (if agent returns it)
- Tool calls tracked via `Tool` primitive

#### Message History Primitives

#### MessageHistoryPrimitive (`tactus/primitives/message_history.py`)

**Status**: ✅ **Fully Implemented**

**Aligned with pydantic-ai:** This primitive manages the `message_history` that gets passed to pydantic-ai's `agent.run_sync(message_history=...)`.

**Features:**
- ✅ `MessageHistory.append({role, content})` - Add messages to history
- ✅ `MessageHistory.inject_system(text)` - Inject system messages
- ✅ `MessageHistory.clear()` - Clear agent's history
- ✅ `MessageHistory.get()` - Get full conversation history (message_history)
- ⚠️ `MessageHistory.load_from_node(node)` - Placeholder (requires graph primitives)
- ⚠️ `MessageHistory.save_to_node(node)` - Placeholder (requires graph primitives)

**Configuration:**
- Procedure-level message_history config in `procedure({message_history = {...}}, function)`
- Agent-level message_history overrides in `agent()` definition
- Integrated with `MessageHistoryManager` for per-agent history management

**Example:**
```lua
procedure({
    message_history = {
        mode = "isolated",
        max_tokens = 120000
    }
}, function()
    MessageHistory.inject_system("Focus on security")
    MessageHistory.append({role = "user", content = "Hello"})
    local history = MessageHistory.get()
    MessageHistory.clear()
end)
```

#### ResultPrimitive (`tactus/primitives/result.py`)

**Status**: ✅ **Fully Implemented**

Wraps pydantic-ai's `RunResult` for Lua access.

**Aligned with pydantic-ai:** Direct mapping to `RunResult.data`, `RunResult.usage()`, `RunResult.new_messages()`, `RunResult.all_messages()`.

**Features:**
- ✅ `result.data` - Response data (text or structured dict)
- ✅ `result.usage` - Token usage stats (prompt_tokens, completion_tokens, total_tokens)
- ✅ `result.new_messages()` - Messages from this turn
- ✅ `result.all_messages()` - Full conversation history
- ✅ `result.cost()` - Token usage (for cost calculation)

**Breaking change:** `Agent.turn()` now returns `ResultPrimitive` instead of raw data. Access response via `result.data`.

**Example:**
```lua
local result = Agent.turn()

-- Access response
Log.info(result.data)

-- Access usage
Log.info("Tokens", {total = result.usage.total_tokens})

-- Access messages
local msgs = result.new_messages()
```

#### Structured Output (output_type)

**Status**: ✅ **Fully Implemented**

**Implementation:**
- `AgentDeclaration.output_type` field in registry (`tactus/core/registry.py`)
- `_create_pydantic_model_from_output_type()` helper in runtime (`tactus/core/runtime.py`)
- Converts Tactus schema to Pydantic model for pydantic-ai's `output_type` parameter

**Aligned with pydantic-ai:** Maps directly to pydantic-ai's `output_type` parameter with automatic validation and retry.

**Example:**
```lua
agent("extractor", {
    output_type = {
        city = {type = "string", required = true},
        country = {type = "string", required = true}
    }
})

-- Agent automatically validates output against schema
local result = Extractor.turn()
Log.info(result.data.city)  -- Type-safe access
```

#### State Primitives

#### StatePrimitive (`tactus/primitives/state.py`)

**Status**: ✅ **Fully Implemented**

- ✅ `State.get(key, default)` - Get value
- ✅ `State.set(key, value)` - Set value
- ✅ `State.increment(key, amount)` - Increment numeric value
- ✅ `State.append(key, value)` - Append to list
- ✅ `State.all()` - Get all state as table

**Implementation:**
- In-memory state dictionary
- Persisted via `StorageBackend` (if backend supports it)

#### Stage Primitives

**Status**: ✅ **Fully Implemented** (see Stages section above)

#### Control Primitives

#### IterationsPrimitive (`tactus/primitives/control.py`)

**Status**: ✅ **Fully Implemented**

- ✅ `Iterations.current()` - Get current iteration count
- ✅ `Iterations.exceeded(max)` - Check if exceeded limit

**Implementation:**
- Incremented by `AgentPrimitive.turn()` automatically
- Can be checked in procedure code for safety limits

#### StopPrimitive (`tactus/primitives/control.py`)

**Status**: ✅ **Fully Implemented**

- ✅ `Stop.requested()` - Check if stop requested
- ✅ `Stop.reason()` - Get stop reason
- ✅ `Stop.success()` - Check if successful stop

**Implementation:**
- Set when `done` tool is called
- Procedure can check this to exit gracefully

#### Tool Primitives

#### ToolPrimitive (`tactus/primitives/tool.py`)

**Status**: ✅ **Fully Implemented**

- ✅ `Tool.called(name)` - Check if tool was called
- ✅ `Tool.last_result(name)` - Get last result
- ✅ `Tool.last_call(name)` - Get full call info (name, args, result)

**Implementation:**
- Tracks all tool calls in `_tool_calls` list
- Maintains `_last_calls` dict for quick lookup
- Records calls automatically when tools execute

#### Graph Primitives

**Specification**: `GraphNode.root()`, `GraphNode.current()`, `GraphNode.create()`, etc.

**Status**: ❌ **Not Implemented**

No graph/tree structure primitives. Procedures are linear sequences, not graphs.

#### Utility Primitives

#### LogPrimitive (`tactus/primitives/log.py`)

**Status**: ✅ **Fully Implemented**

- ✅ `Log.debug(msg)` / `Log.info(msg)` / `Log.warn(msg)` / `Log.error(msg)`
- ✅ Optional context dict: `Log.info("Message", {key = value})`

#### RetryPrimitive (`tactus/primitives/retry.py`)

**Status**: ✅ **Fully Implemented**

- ✅ `Retry.with_backoff(fn, opts)` - Retry function with exponential backoff

#### JsonPrimitive (`tactus/primitives/json.py`)

**Status**: ✅ **Fully Implemented**

- ✅ `Json.encode(table)` - Convert Lua table to JSON string
- ✅ `Json.decode(string)` - Parse JSON string to Lua table

#### FilePrimitive (`tactus/primitives/file.py`)

**Status**: ✅ **Fully Implemented**

- ✅ `File.read(path)` - Read file contents
- ✅ `File.write(path, contents)` - Write file contents
- ✅ `File.exists(path)` - Check if file exists

**Implementation:**
- Uses standard Python file I/O
- No sandbox restrictions (filesystem access allowed)

#### Sleep

**Status**: ✅ **Fully Implemented**

- ✅ `Sleep(seconds)` - Sleep for specified seconds

**Implementation:**
- Wrapper around Python `time.sleep()`
- No checkpoint integration (simple blocking sleep)

---

## Idempotent Execution Model

### Checkpoint Storage

**Specification**: All checkpoints stored in `Procedure.metadata` as JSON.

**Current Implementation:**
- ✅ Checkpoints stored via `StorageBackend` protocol
- ✅ Replay logic implemented in `ExecutionContext.step_run()`
- ❌ Storage format not specified as `Procedure.metadata` structure
- ❌ No explicit checkpoint metadata structure (timestamp, etc.)

**Status**: ✅ **Partially Implemented**

Storage backend determines format. File-based and memory-based implementations exist, but no database schema with `Procedure.metadata` field.

### Replay Behavior

**Status**: ✅ **Fully Implemented**

- First run: executes function and stores result
- Replay: returns cached result immediately
- Works for `Step.run()` checkpoints

### Determinism Requirements

**Status**: ⚠️ **No Enforcement**

Code between checkpoints should be deterministic, but there's no validation. Non-deterministic code will cause replay issues.

### Resume Strategies

**Status**: ✅ **Partially Implemented**

- ✅ Manual resume via `TactusRuntime.execute()` (re-runs procedure)
- ✅ HITL resume (procedure continues when response arrives)
- ❌ No polling daemon (`tactus procedure watch`)
- ❌ No `tactus procedure resume-all` command
- ❌ No automatic resume on Lambda callbacks

---

## CLI Commands

### Implementation (`tactus/cli/app.py`)

**Status**: ✅ **Partially Implemented**

**Implemented Commands:**
- ✅ `tactus run procedure.yaml` - Execute procedure
  - Supports `--storage` (memory, file)
  - Supports `--param key=value`
  - Supports `--openai-api-key`
  
- ✅ `tactus validate procedure.yaml` - Validate YAML syntax and structure
  - Shows procedure info, agents, outputs, parameters
  
- ✅ `tactus version` - Show version

**Missing Commands:**
- ❌ `tactus test procedure.yaml --test-file tests.yaml`
- ❌ `tactus eval procedure.yaml --eval-file evals.yaml`
- ❌ `tactus procedure resume <procedure_id>`
- ❌ `tactus procedure resume-all`
- ❌ `tactus procedure watch --interval 10s`

---

## Storage Backends

### StorageBackend Protocol (`tactus/protocols/storage.py`)

Defines interface for persistence.

**Status**: ✅ **Fully Implemented** (Protocol defined)

**Current Implementations:**
- ✅ `MemoryStorage` (`tactus/adapters/memory.py`) - In-memory storage
- ✅ `FileStorage` (`tactus/adapters/file_storage.py`) - File-based storage

**Missing:**
- ❌ Database-backed storage (PostgreSQL, etc.)
- ❌ Cloud storage (S3, etc.)

---

## BDD Testing Framework

### Gherkin Integration (`tactus/testing/`)

**Status**: ✅ **Fully Implemented**

**Features:**
- ✅ `specifications([[...]])` - Embed Gherkin text in procedure files
- ✅ `step("text", function)` - Custom Lua step definitions
- ✅ `evaluation({...})` - Evaluation configuration
- ✅ Gherkin parser using `gherkin-official` library
- ✅ Comprehensive built-in step library for Tactus primitives
- ✅ Behave integration with programmatic API
- ✅ Parallel execution using multiprocessing
- ✅ Structured Pydantic results (no text parsing)
- ✅ `tactus test` command - Run scenarios once
- ✅ `tactus evaluate` command - Run scenarios N times for consistency
- ✅ Consistency metrics (success rate, timing, flakiness detection)
- ✅ Parser warnings for missing specifications
- ✅ IDE integration via structured log events

**Implementation:**
- `tactus/testing/gherkin_parser.py` - Parse Gherkin to Pydantic models
- `tactus/testing/models.py` - All result models
- `tactus/testing/steps/registry.py` - Step pattern matching
- `tactus/testing/steps/builtin.py` - Built-in step library
- `tactus/testing/steps/custom.py` - Custom Lua steps
- `tactus/testing/context.py` - Test context for step execution
- `tactus/testing/behave_integration.py` - Generate .feature files and step definitions
- `tactus/testing/test_runner.py` - Parallel test execution
- `tactus/testing/evaluation_runner.py` - Multi-run consistency evaluation
- `tactus/testing/events.py` - Structured log events for IDE

**Built-in Steps:**
- Tool steps: `the {tool} tool should be called`, `at least {n} times`, `with {param}={value}`
- Stage steps: `the stage should be {stage}`, `transition from {s1} to {s2}`
- State steps: `the state {key} should be {value}`, `should exist`
- Completion steps: `should complete successfully`, `stop reason should contain {text}`
- Iteration steps: `iterations should be less than {n}`, `between {min} and {max}`
- Parameter steps: `the {param} parameter is {value}`

**Evaluation Metrics:**
- Success rate (% passed)
- Mean/median/stddev duration
- Consistency score (identical behavior across runs)
- Flakiness detection (some pass, some fail)

**Example:**
```lua
specifications([[
Feature: Agent Workflow
  Scenario: Completes task
    Given the procedure has started
    When the worker agent takes turns
    Then the done tool should be called
]])

step("custom validation", function()
  assert(State.get("count") > 5)
end)
```

```bash
tactus test procedure.tac
tactus evaluate procedure.tac --runs 10
```

## Missing Features Summary

### Critical Missing Features

1. **Procedure Recursion/Composition** ❌
   - No `Procedure` primitive
   - Cannot invoke other procedures
   - Blocks procedure composition

2. **Guards** ❌
   - No pre-execution validation
   - YAML not parsed

3. **Dependencies** ❌
   - No upfront validation
   - Tools checked only at runtime

4. **Inline Procedures** ❌
   - `procedures:` section not parsed
   - Cannot define helper procedures

5. **Summarization Prompts** ❌
   - `return_prompt`, `error_prompt`, `status_prompt` not implemented
   - No final summary turns

6. **Lambda Durable Execution Context** ❌
   - Only local context exists
   - No AWS Lambda integration

7. **System.alert()** ❌
   - No system-level alerts
   - Only `Human.notify()` exists

### Partially Implemented Features

1. **Execution Contexts** ⚠️
   - Local context: ✅
   - Lambda context: ❌

2. **Template Variables** ⚠️
   - `params`, `state`: ✅
   - `outputs`, `context`, `prepared`, `env`: ❌

3. **Agent Features** ⚠️
   - Core functionality: ✅
   - `prepare` hook: ❌
   - `filter`: ❌
   - `response.retries`: ❌

4. **CLI Commands** ⚠️
   - Basic commands: ✅
   - Advanced commands: ❌

---

## File Map

```
tactus/
├── core/
│   ├── runtime.py              # Main TactusRuntime engine
│   ├── execution_context.py    # Execution context abstraction
│   ├── lua_sandbox.py          # Lua execution environment
│   ├── yaml_parser.py          # YAML parsing and validation
│   └── output_validator.py     # Output schema validation
│
├── primitives/
│   ├── agent.py                # AgentPrimitive (LLM integration)
│   ├── state.py                # StatePrimitive
│   ├── tool.py                 # ToolPrimitive
│   ├── human.py                # HumanPrimitive (HITL)
│   ├── step.py                 # StepPrimitive, CheckpointPrimitive
│   ├── stage.py                # StagePrimitive
│   ├── control.py              # IterationsPrimitive, StopPrimitive
│   ├── log.py                  # LogPrimitive
│   ├── json.py                 # JsonPrimitive
│   ├── retry.py                # RetryPrimitive
│   └── file.py                 # FilePrimitive
│
├── protocols/
│   ├── storage.py              # StorageBackend protocol
│   ├── hitl.py                 # HITLHandler protocol
│   └── models.py               # Data models (HITLRequest, etc.)
│
├── adapters/
│   ├── memory.py               # MemoryStorage implementation
│   ├── file_storage.py         # FileStorage implementation
│   ├── cli_hitl.py             # CLIHITLHandler implementation
│   └── mcp.py                  # MCP server adapter
│
└── cli/
    └── app.py                  # CLI application (Typer)
```

---

## Implementation Roadmap

To align the implementation with the specification:

### High Priority
1. **Procedure Primitive** - Enable recursion and composition
2. **Guards** - Add pre-execution validation
3. **Dependencies** - Add upfront validation
4. **Summarization Prompts** - Implement return/error/status prompts

### Medium Priority
5. **Inline Procedures** - Parse and support `procedures:` section
6. **Agent `prepare` hook** - Enable `prepared` template namespace
7. **System.alert()** - System-level alert infrastructure
8. **Template variables** - Add `context`, `env`, `outputs` support

### Low Priority
9. **Lambda Durable Context** - AWS Lambda integration
10. **Advanced CLI commands** - test, eval, resume-all, watch
11. **Agent filters** - ComposedFilter, TokenBudget, etc.
12. **Graph primitives** - Tree structure support

---

## Notes

- This implementation guide reflects the state of the codebase as of the last analysis
- Status indicators:
  - ✅ Fully Implemented
  - ⚠️ Partially Implemented
  - ❌ Not Implemented
- For the most up-to-date specification, see [SPECIFICATION.md](SPECIFICATION.md)
