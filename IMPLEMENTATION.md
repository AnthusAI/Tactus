# Tactus Implementation Guide

This document maps the [SPECIFICATION.md](SPECIFICATION.md) to the actual codebase implementation. It describes where each feature is implemented, what's complete, and what's missing.

**Purpose**: After reading the specification, use this document to understand how features are actually implemented in the code and to identify gaps between the spec and current implementation.

---

## Current Status Summary

**All 6 Durability Phases Complete** (as of December 2024)

Tactus now has comprehensive durable execution capabilities:

- ✅ **Position-based checkpointing** - Natural loop handling, no named checkpoints
- ✅ **Input/Output/State syntax** - Breaking change from params/outputs (schema-validated)
- ✅ **Model primitive** - ML inference with HTTP/PyTorch backends
- ✅ **Sub-procedure auto-checkpointing** - Direct function call syntax
- ✅ **Explicit checkpoint primitive** - Global `checkpoint()` function
- ✅ **Script mode** - Top-level input/output declarations
- ✅ **Dependencies** - Resource injection with unified mocking

**Test Coverage**: 146/146 pytest + 233/233 behave scenarios passing

See [docs/DURABILITY.md](/Users/ryan.porter/Projects/Tactus/docs/DURABILITY.md) for comprehensive durability design documentation.

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

Abstraction layer for position-based checkpointing and HITL operations.

**Components:**
- `ExecutionContext` - Abstract base class defining protocol
- `BaseExecutionContext` - Base implementation using pluggable storage and HITL handlers
- `InMemoryExecutionContext` - Simple in-memory variant

**Position-Based Checkpointing:**

All checkpoints are tracked by execution position, not name. This enables:
- Natural loop handling (same code, different positions)
- Automatic sub-procedure checkpointing
- Deterministic replay from start
- Execution log as single source of truth

**Key Methods:**
- `checkpoint(fn, checkpoint_type)` - Execute function with position-based checkpoint/replay
- `wait_for_human(...)` - Suspend execution until human responds
- `checkpoint_clear_all()` - Clear all checkpoints (testing)
- `checkpoint_clear_after(position)` - Clear from position onwards (testing)
- `next_position()` - Get next checkpoint position

**Execution Log Structure:**

```python
{
    "procedure_id": "run_abc123",
    "execution_log": [
        {
            "position": 0,
            "type": "agent_turn",
            "result": {...},
            "timestamp": "2025-01-15T10:30:00Z"
        },
        {
            "position": 1,
            "type": "model_predict",
            "result": "billing",
            "timestamp": "2025-01-15T10:30:01Z"
        }
    ],
    "state": {...},
    "replay_index": 2
}
```

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
- Input schema (`input`)
- Output schema (`output`)
- State schema (`state`)
- Agents definitions
- Procedure Lua code (basic syntax check)

**Status**: ✅ **Partially Implemented**

**Missing Validations:**
- ❌ `guards` section (not parsed or validated)
- ❌ `hitl` declarative configuration (parsed but not validated)
- ❌ `procedures` inline definitions (not parsed)
- ❌ `stages` declarations (not validated)
- ❌ `async`, `max_depth`, `max_turns`, `checkpoint_interval` (not parsed)
- ❌ `return_prompt`, `error_prompt`, `status_prompt` (not parsed)

### Input (formerly Parameters)

#### Implementation: DSL Stubs + Registry

**Lua DSL Format (.tac files):**

Input is now defined inside the `procedure()` config table:

```lua
procedure({
    input = {
        task = {
            type = "string",
            required = true
        }
    }
}, function()
    local task = input.task
    -- ...
end)
```

**Script Mode Support:**

Top-level input declarations for simple scripts:

```lua
input {
    task = {type = "string", required = true}
}

-- Top-level code acts as main procedure
Worker.turn({inject = input.task})
return {result = "done"}
```

**How it works:**
1. The `procedure()` stub in `dsl_stubs.py` accepts two arguments: config table and function
2. When config contains `input`, each parameter is registered via `builder.register_parameter()`
3. Runtime converts registry to config dict format for compatibility
4. Input values injected into Lua sandbox with default values
5. Context values override defaults
6. Input values accessible in Lua as `input.field_name`

**Location**:
- DSL Stub: `tactus/core/dsl_stubs.py` (updated `_procedure` function)
- Registry: `tactus/core/registry.py` (`RegistryBuilder.register_parameter()`)
- Injection: `tactus/core/runtime.py` (`_inject_primitives()`)

**Template Support**: ✅ Input accessible in templates via `{input.name}`

**Status**: ✅ **Fully Implemented**

### Output (formerly Outputs)

#### Implementation: DSL Stubs + Registry + OutputValidator

**Lua DSL Format (.tac files):**

Output is now defined inside the `procedure()` config table:

```lua
procedure({
    output = {
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

**Script Mode Support:**

Top-level output declarations for simple scripts:

```lua
output {
    result = {type = "string", required = true}
}

-- Top-level code returns output
Worker.turn()
return {result = "done"}
```

**How it works:**
1. The `procedure()` stub in `dsl_stubs.py` accepts two arguments: config table and function
2. When config contains `output`, each output field is registered via `builder.register_output()`
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

### Script Mode (Phase 6)

**Status**: ✅ **Fully Implemented**

Script mode allows simple procedures to be written without explicit `procedure()` wrappers. Top-level code becomes the entry point, making Tactus feel more like a script than a framework.

#### Three Approaches

**1. Simplest (no schemas):**

```lua
-- No input/output declarations needed
Worker = agent "worker" {
    model = "claude-sonnet-4-20250514",
    system_prompt = "You are a helpful assistant."
}

Worker.turn({inject = input.text})
return {result = Worker.output}
```

**2. With Schema Declarations:**

```lua
input {
    text = {type = "string", required = true},
    language = {type = "string", default = "en"}
}

output {
    result = {type = "string", required = true}
}

Worker = agent "worker" {
    model = "claude-sonnet-4-20250514"
}

Worker.turn({inject = input.text})
return {result = Worker.output}
```

**3. Hybrid (sub-procedures + top-level main):**

```lua
input {document = {type = "string"}}
output {result = {type = "string"}}

-- Helper sub-procedure
summarize_chunk = procedure "summarize_chunk" {
    input = {chunk = {type = "string"}},
    output = {summary = {type = "string"}},
    run = function()
        Summarizer = agent "summarizer" {
            model = "claude-sonnet-4-20250514"
        }
        Summarizer.turn({inject = input.chunk})
        return {summary = Summarizer.output}
    end
}

-- Top-level code acts as main procedure
chunks = split_text(input.document, 1000)
state.summaries = {}

for i, chunk in ipairs(chunks) do
    result = summarize_chunk({chunk = chunk})
    state.summaries[i] = result.summary
end

return {result = join_summaries(state.summaries)}
```

#### How It Works

1. Runtime detects top-level `input {}` and `output {}` declarations
2. If no explicit `main` procedure exists, top-level code is wrapped in implicit main
3. Top-level code can:
   - Access `input` table (from runtime context)
   - Define agents and models
   - Call sub-procedures
   - Mutate `state` table
   - Return output table
4. All durability features work identically (checkpointing, replay, HITL)

#### When to Use

**Use Script Mode for:**
- Simple linear workflows
- Quick prototypes
- Single-agent tasks
- Learning Tactus

**Use Explicit Procedures for:**
- Multiple reusable procedures
- Complex state management
- Clear separation of concerns
- Production systems with multiple entry points

#### Implementation Details

**Location:**
- DSL Stub: `tactus/core/dsl_stubs.py` (`input()`, `output()` functions)
- Runtime: `tactus/core/runtime.py` (implicit main wrapping)
- Registry: `tactus/core/registry.py` (top-level schema tracking)

**Compatibility:**

Script mode files can be gradually converted to explicit procedures without breaking:

```lua
-- Before (script mode)
input {text = {type = "string"}}
Worker.turn({inject = input.text})
return {result = Worker.output}

-- After (explicit procedure)
main = procedure "main" {
    input = {text = {type = "string"}},
    output = {result = {type = "string"}},
    run = function()
        Worker = agent "worker" {...}
        Worker.turn({inject = input.text})
        return {result = Worker.output}
    end
}
```

### Summarization Prompts

**Specification Sections:**
- `return_prompt:` - Injected when procedure completes successfully
- `error_prompt:` - Injected when procedure fails
- `status_prompt:` - Injected for async status updates

**Status**: ✅ **Partially Implemented**

These prompts are now parsed from DSL, stored in registry, and logged at appropriate times. Full implementation (injecting prompts to agents for summary generation) is deferred for future enhancement.

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

### Dependencies (Resource Injection)

**Status**: ✅ **Fully Implemented**

Tactus provides first-class dependency injection for external resources, enabling procedures to declare dependencies on HTTP clients, databases, and other services.

#### Overview

Dependencies are external resources that procedures need to function:
- HTTP clients for API calls
- PostgreSQL databases
- Redis caches
- Custom resources

The runtime automatically creates, manages, and cleans up these resources, injecting them into agent dependencies for use in tools.

#### Declaration Syntax

```lua
procedure "customer_lookup" {
    dependencies = {
        api_client = {
            type = "http_client",
            base_url = "https://api.example.com",
            headers = {
                ["Authorization"] = "Bearer " .. env.API_KEY
            }
        },
        db = {
            type = "postgres",
            connection_string = env.DATABASE_URL
        },
        cache = {
            type = "redis",
            url = env.REDIS_URL
        }
    },
    input = {...},
    output = {...},
    run = function()
        -- Dependencies available to agents via AgentDeps
        Worker.turn()
        return {...}
    end
}
```

#### Supported Resource Types

| Type | Description | Configuration |
|------|-------------|---------------|
| `http_client` | HTTPX async client | `base_url`, `headers`, `timeout` |
| `postgres` | AsyncPG connection pool | `connection_string`, `min_size`, `max_size` |
| `redis` | Redis async client | `url`, `decode_responses` |

#### Implementation

**Core Infrastructure:**

1. **ResourceFactory** (`tactus/core/dependencies/registry.py`)
   - Creates real resources (httpx, asyncpg, redis clients)
   - Handles async initialization
   - Configures connection pools

2. **ResourceManager** (`tactus/core/dependencies/registry.py`)
   - Manages resource lifecycle
   - Automatic cleanup on procedure completion
   - Resource sharing across nested procedures

3. **Dynamic AgentDeps Generation** (`tactus/primitives/deps_generator.py`)
   - Generates custom `AgentDeps` dataclass with user dependencies
   - Proper field ordering (fields without defaults before fields with defaults)
   - Injects resources into Pydantic AI agents

**Modified Files:**
- `tactus/core/registry.py` - Added `DependencyDeclaration` model
- `tactus/core/dsl_stubs.py` - Parses `dependencies` from `procedure()` calls
- `tactus/primitives/agent.py` - Uses dynamic AgentDeps generation
- `tactus/core/runtime.py` - Added `_initialize_dependencies()` and cleanup

#### Mocking System

**Unified Mock Registry:**

All dependencies (resources + HITL) can be mocked for testing:

```python
# tactus/testing/mock_registry.py
class UnifiedMockRegistry:
    def __init__(self):
        self.http_mocks: Dict[str, MockHTTPClient] = {}
        self.hitl_mock: MockHITLHandler = MockHITLHandler()
        self.db_mocks: Dict[str, MockDatabase] = {}
```

**Mock Implementations:**
- `MockHTTPClient` (`tactus/testing/mock_dependencies.py`)
- `MockDatabase` (`tactus/testing/mock_dependencies.py`)
- `MockRedis` (`tactus/testing/mock_dependencies.py`)

**Gherkin Mock Configuration:**

Configure mocks via natural language steps in BDD tests:

```gherkin
Feature: Customer Lookup
  Scenario: Successful lookup
    # Configure HTTP mock response
    Given the api_client returns '{"name": "John", "status": "active"}'

    # Configure HITL mock
    And Human.approve will return true

    When the Worker agent takes turn
    Then the done tool should be called

    # Assert mock was called
    And the api_client should have been called
```

**Mock Steps** (`tactus/testing/steps/mock_steps.py`):
- `Given the {dep_name} returns '{response}'` - Configure HTTP response
- `And Human.approve will return {value}` - Configure HITL behavior
- `Then the {dep_name} should have been called` - Assert dependency usage

#### Testing Modes

```bash
# Unit tests with mocked dependencies (fast)
tactus test procedure.tac --mocked

# Integration tests with real services (requires infrastructure)
tactus test procedure.tac --integration
```

#### Nested Procedures

Child procedures **share** parent dependencies:
- Same HTTP client instances (efficient connection reuse)
- Same database connection pools
- Same cache connections

```lua
-- Parent declares dependencies
main = procedure "main" {
    dependencies = {
        api = {type = "http_client", base_url = "..."}
    },
    run = function()
        -- Child procedures inherit parent's dependencies
        result = helper_procedure({...})
    end
}
```

#### Checkpoint/Restart Behavior

Dependencies are **recreated** on restart:
- Configuration saved in checkpoint
- Instances are ephemeral (not serialized)
- Fresh connections established on resume

#### Example Usage

```lua
procedure "weather_lookup" {
    dependencies = {
        weather_api = {
            type = "http_client",
            base_url = "https://api.weatherapi.com/v1",
            headers = {
                ["key"] = env.WEATHER_API_KEY
            },
            timeout = 10
        }
    },
    input = {
        location = {type = "string", required = true}
    },
    output = {
        temperature = {type = "number"},
        condition = {type = "string"}
    },
    run = function()
        Worker = agent "worker" {
            model = "claude-sonnet-4-20250514",
            system_prompt = "You look up weather information.",
            tools = {weather_lookup_tool}  -- Tool uses weather_api from deps
        }

        Worker.turn({inject = "Get weather for " .. input.location})
        return {
            temperature = state.temp,
            condition = state.condition
        }
    end
}
```

#### Current Limitations

1. **MCP Tool Integration**: Dependencies are injected into AgentDeps, but automatic MCP tool generation is not yet implemented. Tools must be manually created to expose dependencies.

2. **Resource Types**: Currently supports http_client, postgres, redis. More types (S3, MongoDB, message queues) can be added.

3. **Lazy Loading**: Dependencies are initialized at procedure start. Lazy initialization (on first use) is not yet supported.

#### Files

**New Files:**
- `tactus/core/dependencies/registry.py` - ResourceFactory, ResourceManager
- `tactus/primitives/deps_generator.py` - Dynamic AgentDeps generation
- `tactus/testing/mock_dependencies.py` - Mock implementations
- `tactus/testing/mock_registry.py` - Unified mock registry
- `tactus/testing/steps/mock_steps.py` - Gherkin mock steps

**Modified Files:**
- `tactus/core/registry.py` - DependencyDeclaration
- `tactus/core/dsl_stubs.py` - Dependency parsing
- `tactus/primitives/agent.py` - Dynamic deps usage
- `tactus/core/runtime.py` - Initialization and cleanup
- `tactus/testing/context.py` - Mock injection
- `tactus/testing/test_runner.py` - --mocked flag
- `tactus/testing/behave_integration.py` - Mock passthrough

**Total**: ~1,500+ lines of production code + tests + docs

#### Philosophy

Dependencies follow Tactus's "thin layer over Pydantic AI" philosophy by mapping directly to Pydantic AI's dependency injection system (`AgentDeps`), while adding:
- Automatic resource lifecycle management
- Unified mocking for testing
- Natural Lua declaration syntax

### Template Variable Namespaces

**Specification**: `input`, `output`, `context`, `state`, `prepared`, `env`

**Current Implementation:**
- ✅ `input` - Fully supported (formerly `params`)
- ✅ `state` - Fully supported (via `StatePrimitive`)
- ❌ `output` - Not available (only in return_prompt, which isn't implemented)
- ❌ `context` - Not implemented
- ❌ `prepared` - Not implemented (agent `prepare` hook not implemented)
- ❌ `env` - Not implemented

**Status**: ✅ **Partially Implemented** (input, state only)

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
- ✅ System prompt with template variables (`{input.*}`, `{state.*}`)
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

### Model Primitive (Phase 3: ML Inference)

#### ModelPrimitive (`tactus/primitives/model.py`)

**Status**: ✅ **Fully Implemented**

The Model primitive provides durability for generic ML inference operations, distinct from Agent (conversational LLM) operations.

**Purpose:**
- Classification (intent, sentiment, NER)
- Extraction (entities, facts, quotes)
- Embeddings (semantic search, clustering)
- Custom ML inference (any trained model)

**Features:**
- ✅ Multiple backend support (HTTP, PyTorch, more planned)
- ✅ Automatic checkpointing via `context.checkpoint()`
- ✅ Cached results on replay
- ✅ Configurable timeout and retry logic

**Backend Protocol** (`tactus/backends/model_backend.py`):

Defines standard interface for model backends:

```python
class ModelBackend(Protocol):
    def predict(self, input_data: Any) -> Any:
        """Run inference and return result."""
        pass
```

**Supported Backends:**

1. **HTTP Backend** (`tactus/backends/http_backend.py`)
   - REST endpoint inference
   - Configurable timeout
   - JSON request/response

   ```lua
   Classifier = model "classifier" {
       type = "http",
       endpoint = "http://ml-service:8000/predict",
       timeout = 30
   }
   ```

2. **PyTorch Backend** (`tactus/backends/pytorch_backend.py`)
   - Load `.pt` model files
   - CPU/GPU inference
   - Custom preprocessing

   ```lua
   IntentModel = model "intent" {
       type = "pytorch",
       path = "models/intent.pt",
       device = "cpu"
   }
   ```

**Planned Backends:**
- BERT/HuggingFace transformers
- Scikit-learn models
- ONNX runtime
- SageMaker endpoints
- Sentence transformers

**Usage in Lua:**

```lua
-- Define model
IntentClassifier = model "intent_classifier" {
    type = "http",
    endpoint = "http://localhost:8000/classify",
    timeout = 10
}

-- Single prediction (auto-checkpointed)
state.intent = IntentClassifier.predict(input.message)

-- Use result
if state.intent == "billing" then
    BillingAgent.turn()
elseif state.intent == "technical" then
    TechAgent.turn()
end
```

**Checkpoint Behavior:**

Each `.predict()` call creates a checkpoint entry:

```python
{
    "position": 0,
    "type": "model_predict",
    "model_name": "intent_classifier",
    "result": "billing",
    "timestamp": "2025-01-15T10:30:00Z",
    "duration_ms": 45
}
```

On replay, cached result returned without re-running inference.

**Location:**
- Primitive: `tactus/primitives/model.py`
- Backend Protocol: `tactus/backends/model_backend.py`
- HTTP Backend: `tactus/backends/http_backend.py`
- PyTorch Backend: `tactus/backends/pytorch_backend.py`

### Invoking Procedures (Phase 4: Sub-Procedure Auto-Checkpointing)

#### ProcedurePrimitive (`tactus/primitives/procedure.py`)

**Status**: ✅ **Partially Implemented**

**Implemented:**
- ✅ Synchronous procedure invocation with automatic checkpointing
- ✅ Direct function call syntax (procedure returns callable)
- ✅ Nested execution contexts
- ✅ Input/output validation
- ✅ Checkpoint replay for sub-procedures

**Not Implemented:**
- ❌ `Procedure.spawn(name, params)` - Async invocation
- ❌ `Procedure.status(handle)` - Get status
- ❌ `Procedure.wait(handle)` - Wait for completion
- ❌ `Procedure.inject(handle, message)` - Send guidance
- ❌ `Procedure.cancel(handle)` - Abort
- ❌ `Procedure.wait_any(handles)` - Wait for first
- ❌ `Procedure.wait_all(handles)` - Wait for all

**Sub-Procedure Auto-Checkpointing:**

When a procedure is called, the entire invocation is automatically checkpointed:

```lua
-- Define helper procedure
summarize_chunk = procedure "summarize_chunk" {
    input = {chunk = {type = "string"}},
    output = {summary = {type = "string"}},
    run = function()
        Summarizer = agent "summarizer" {
            model = "claude-sonnet-4-20250514"
        }
        Summarizer.turn({inject = input.chunk})
        return {summary = Summarizer.output}
    end
}

-- Main procedure calls helper (auto-checkpointed)
main = procedure "main" {
    input = {document = {type = "string"}},
    output = {result = {type = "string"}},
    state = {summaries = {type = "array", default = {}}},
    run = function()
        chunks = split_text(input.document, 1000)

        for i, chunk in ipairs(chunks) do
            result = summarize_chunk({chunk = chunk})  -- Checkpointed!
            state.summaries[i] = result.summary
        end

        return {result = join_summaries(state.summaries)}
    end
}
```

**Checkpoint Entry:**

Each sub-procedure call creates a checkpoint:

```python
{
    "position": 3,
    "type": "procedure_call",
    "procedure_name": "summarize_chunk",
    "input": {"chunk": "..."},
    "result": {"summary": "..."},
    "timestamp": "2025-01-15T10:30:05Z",
    "duration_ms": 2341
}
```

**Replay Behavior:**

On replay, completed sub-procedure calls return cached results without re-execution. This includes all nested agent turns, model predictions, and HITL interactions within the sub-procedure.

**Implementation Details:**

1. `procedure()` DSL stub returns a callable that wraps the run function
2. Callable invocation goes through `context.checkpoint()`
3. Nested execution context created for sub-procedure
4. Input validated against schema
5. Sub-procedure executes (or replays)
6. Output validated against schema
7. Result cached in parent's execution log

**Location:**
- Primitive: `tactus/primitives/procedure.py`
- DSL Stub: `tactus/core/dsl_stubs.py` (`_procedure` function)
- Registry: `tactus/core/registry.py`

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
- Delegates to `ExecutionContext.checkpoint()`
- On first execution: runs function and caches result
- On replay: returns cached result immediately

**Note**: Step primitives are optional. All agent turns, model predictions, and procedure calls are automatically checkpointed without requiring explicit steps.

#### Explicit Checkpoint Primitive (Phase 5)

**Status**: ✅ **Fully Implemented**

**Global Function**: `checkpoint()`

**Purpose**: Manually save state without creating a suspend point.

**When to Use:**

1. **After expensive pure computations:**
   ```lua
   state.embeddings = compute_embeddings(large_document)
   state.clusters = cluster_embeddings(state.embeddings)
   checkpoint()  -- Save before proceeding

   Worker.turn({inject = state.clusters})
   ```

2. **Before risky operations:**
   ```lua
   state.prepared_data = prepare_for_upload(raw_data)
   checkpoint()  -- Save preparation work

   external_api.upload(state.prepared_data)  -- Might fail
   ```

3. **Periodic saves in long computations:**
   ```lua
   for i, batch in ipairs(batches) do
       state.results[i] = process_batch(batch)

       if i % 10 == 0 then
           checkpoint()  -- Every 10 batches
       end
   end
   ```

**What It Does NOT Do:**

Explicit checkpoints do **not** create suspend points. They simply persist current state. For suspend points (waiting for external input), use HITL primitives like `Human.approve()` or `Human.input()`.

**Checkpoint Entry:**

```python
{
    "position": 5,
    "type": "explicit_checkpoint",
    "state_snapshot": {...},
    "timestamp": "2025-01-15T10:30:10Z"
}
```

**Location**: `tactus/primitives/step.py` (`checkpoint` function)

#### CheckpointPrimitive (`tactus/primitives/step.py`)

**Status**: ✅ **Fully Implemented**

- ✅ `Checkpoint.clear_all()` - Clear all checkpoints (execution log)
- ✅ `Checkpoint.clear_after(position)` - Clear from position onwards

**Usage**: Testing and debugging checkpoint replay behavior. These are utility functions for test scenarios, not for production use.

#### Human Interaction Primitives

**Status**: ✅ **Fully Implemented** (see HITL section above)

#### Agent Primitives

**Status**: ✅ **Fully Implemented**

- ✅ `AgentName.turn()` - Execute agent turn
- ✅ `AgentName.turn({inject = "..."})` - Turn with injected message
- ✅ `AgentName.turn({tools = {...}})` - Turn with specific tools
- ✅ `AgentName.turn({tools = {}})` - Turn with no tools
- ✅ Per-turn model parameter overrides (temperature, max_tokens, top_p, etc.)

**Per-Turn Overrides:**

The `turn()` method now accepts an optional table to override behavior for a single turn:
- `inject` - Inject a specific message for this turn
- `tools` - Override available tools (empty list = no tools)
- `temperature`, `max_tokens`, `top_p` - Override model settings

**Common pattern - Tool result summarization:**
```lua
repeat
    Researcher.turn()  -- Agent has all tools
    
    if Tool.called("search") then
        Researcher.turn({
            inject = "Summarize the search results",
            tools = {}  -- No tools for summarization
        })
    end
until Tool.called("done")
```

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
- ✅ `State.set(key, value)` - Set value with schema validation
- ✅ `State.increment(key, amount)` - Increment numeric value
- ✅ `State.append(key, value)` - Append to list
- ✅ `State.all()` - Get all state as table

**State Schema Support:**

Procedures declare state schema for validation and initialization:

```lua
procedure "order_fulfillment" {
    state = {
        order_id = {type = "string", required = true},
        status = {
            type = "string",
            default = "pending",
            enum = {"pending", "processing", "shipped", "delivered"}
        },
        shipping_address = {type = "table"},
        attempts = {type = "number", default = 0}
    }
}
```

**Features:**

1. **Initialization with Defaults:**
   - State fields with `default` values are automatically initialized
   - Available immediately when procedure starts

2. **Runtime Validation:**
   - Type checking when `State.set()` is called
   - Warns on type mismatches (doesn't throw)
   - Validates against enum constraints

3. **Schema-Defined Fields:**
   ```lua
   state = {
       counter = {type = "number", default = 0},
       items = {type = "array", default = {}},
       metadata = {type = "table", default = {}}
   }
   ```

4. **Persistence:**
   - State persisted with each checkpoint
   - Restored on replay
   - Survives procedure suspension (HITL)

**Implementation:**
- In-memory state dictionary
- Schema stored in `StatePrimitive._schema`
- Default initialization in `__init__`
- Type validation in `set()` method
- State persisted via `ExecutionContext` after each checkpoint

**Location**: `tactus/primitives/state.py`

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

**Implementation**: Position-based execution log with state snapshots.

**Current Implementation:**
- ✅ Position-based checkpointing (not name-based)
- ✅ Execution log with position, type, result, timestamp
- ✅ Checkpoints stored via `StorageBackend` protocol
- ✅ Replay logic implemented in `ExecutionContext.checkpoint()`
- ✅ State persisted with each checkpoint
- ✅ Metadata structure includes timestamps and durations

**Checkpoint Structure:**

```python
{
    "procedure_id": "run_abc123",
    "execution_log": [
        {
            "position": 0,
            "type": "agent_turn",
            "agent_name": "worker",
            "result": {...},
            "timestamp": "2025-01-15T10:30:00Z",
            "duration_ms": 1523
        },
        {
            "position": 1,
            "type": "model_predict",
            "model_name": "intent_classifier",
            "result": "billing",
            "timestamp": "2025-01-15T10:30:02Z",
            "duration_ms": 45
        },
        {
            "position": 2,
            "type": "hitl_approval",
            "status": "completed",
            "request": {...},
            "result": true,
            "timestamp": "2025-01-15T10:30:05Z"
        },
        {
            "position": 3,
            "type": "procedure_call",
            "procedure_name": "helper",
            "input": {...},
            "result": {...},
            "timestamp": "2025-01-15T10:30:08Z",
            "duration_ms": 2341
        },
        {
            "position": 4,
            "type": "explicit_checkpoint",
            "state_snapshot": {...},
            "timestamp": "2025-01-15T10:30:10Z"
        }
    ],
    "state": {
        "category": "billing",
        "attempts": 1,
        "completed": false
    },
    "status": "running",
    "replay_index": 5
}
```

**Checkpoint Types:**

| Type | Description | Created By |
|------|-------------|------------|
| `agent_turn` | LLM conversation turn | `AgentPrimitive.turn()` |
| `model_predict` | ML inference | `ModelPrimitive.predict()` |
| `procedure_call` | Sub-procedure invocation | Procedure callable |
| `hitl_approval` | Human approval request | `Human.approve()` |
| `hitl_input` | Human input request | `Human.input()` |
| `hitl_review` | Human review request | `Human.review()` |
| `explicit_checkpoint` | Manual state save | `checkpoint()` function |
| `step` | Named step | `Step.run()` (optional) |

**Status**: ✅ **Fully Implemented**

Storage backend determines persistence format. File-based, memory-based, and future database implementations all use the same checkpoint structure.

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
  
- ✅ `tactus test procedure.yaml` - Run BDD specifications
  - Supports `--scenario` filter
  - Supports `--parallel` execution
  - Supports `--runs N` for consistency evaluation
  
- ✅ `tactus eval procedure.yaml` - Run Pydantic evaluations
  - Supports `--runs` count
  - Supports `--parallel` execution
  
- ✅ `tactus version` - Show version

**Missing Commands:**
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
- ✅ Gherkin parser using `gherkin-official` library
- ✅ Comprehensive built-in step library for Tactus primitives
- ✅ Behave integration with programmatic API
- ✅ Parallel execution using multiprocessing
- ✅ `tactus test` command - Run scenarios (use `--runs N` for consistency)
- ✅ Consistency metrics (success rate, timing, flakiness detection)

### Pydantic Evaluations (`tactus/testing/`)

**Status**: ✅ **Fully Implemented**

**Features:**
- ✅ `evaluations({...})` - Evaluation configuration in Lua
- ✅ Pydantic AI Evals integration
- ✅ External dataset loading (JSONL, JSON, CSV)
- ✅ `tactus eval` command - Run evaluations against dataset
- ✅ Advanced evaluators (Regex, JSON Schema, Range, Trace Inspection)
- ✅ CI/CD Thresholds
- ✅ Structured Pydantic results (no text parsing)
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

### Recently Completed (All 6 Durability Phases)

1. **✅ Phase 1: Position-Based Execution Log**
   - Position-based checkpointing (not name-based)
   - Execution log as single source of truth
   - Natural loop handling

2. **✅ Phase 2: Input/Output/State Syntax**
   - Breaking change from `params`/`outputs` to `input`/`output`
   - State schema with defaults and validation
   - Script mode support

3. **✅ Phase 3: Model Primitive**
   - ML inference primitive (distinct from Agent)
   - HTTP and PyTorch backends
   - Automatic checkpointing

4. **✅ Phase 4: Sub-Procedure Auto-Checkpointing**
   - Direct function call syntax for procedures
   - Automatic checkpoint on invocation
   - Nested execution contexts

5. **✅ Phase 5: Explicit Checkpoint Primitive**
   - Global `checkpoint()` function
   - Manual state persistence
   - No suspend point (continues execution)

6. **✅ Phase 6: Script Mode**
   - Top-level `input {}` and `output {}` declarations
   - Implicit main procedure wrapping
   - Mixed mode (sub-procedures + top-level)

7. **✅ Dependencies (Resource Injection)**
   - HTTP clients, PostgreSQL, Redis
   - Automatic lifecycle management
   - Unified mocking system for testing

### Critical Missing Features

1. **Guards** ❌
   - No pre-execution validation
   - YAML not parsed

2. **Inline Procedures** ❌
   - `procedures:` section not parsed
   - Cannot define helper procedures in YAML (use Lua DSL instead)

3. **Lambda Durable Execution Context** ❌
   - Only local context exists
   - No AWS Lambda integration

4. **System.alert()** ❌
   - No system-level alerts
   - Only `Human.notify()` exists

5. **Async Procedure Spawning** ❌
   - No `Procedure.spawn()` for async invocation
   - No `Procedure.wait()`, `Procedure.wait_all()`, etc.
   - Only synchronous sub-procedure calls

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
   - Session filters: ✅ (basic implementation)
   - `response.retries`: ❌

4. **Summarization Prompts** ⚠️
   - Parsed and stored: ✅
   - Logged at appropriate times: ✅
   - Full agent injection for summaries: ❌ (deferred)

5. **CLI Commands** ⚠️
   - Basic commands: ✅
   - Advanced commands: ❌

---

## File Map

```
tactus/
├── core/
│   ├── runtime.py              # Main TactusRuntime engine
│   ├── execution_context.py    # Execution context abstraction (position-based)
│   ├── lua_sandbox.py          # Lua execution environment
│   ├── yaml_parser.py          # YAML parsing and validation
│   ├── output_validator.py     # Output schema validation
│   ├── registry.py             # RegistryBuilder for DSL declarations
│   ├── dsl_stubs.py            # Lua DSL stubs (procedure, agent, model, etc.)
│   └── dependencies/
│       └── registry.py         # ResourceFactory, ResourceManager
│
├── primitives/
│   ├── agent.py                # AgentPrimitive (LLM integration)
│   ├── model.py                # ModelPrimitive (ML inference) [NEW]
│   ├── procedure.py            # ProcedurePrimitive (sub-procedures) [NEW]
│   ├── state.py                # StatePrimitive (with schema validation)
│   ├── tool.py                 # ToolPrimitive
│   ├── human.py                # HumanPrimitive (HITL)
│   ├── step.py                 # StepPrimitive, checkpoint() function
│   ├── stage.py                # StagePrimitive
│   ├── control.py              # IterationsPrimitive, StopPrimitive
│   ├── log.py                  # LogPrimitive
│   ├── json.py                 # JsonPrimitive
│   ├── retry.py                # RetryPrimitive
│   ├── file.py                 # FilePrimitive
│   ├── message_history.py      # MessageHistoryPrimitive
│   ├── result.py               # ResultPrimitive
│   └── deps_generator.py       # Dynamic AgentDeps generation [NEW]
│
├── backends/
│   ├── model_backend.py        # ModelBackend protocol [NEW]
│   ├── http_backend.py         # HTTP model backend [NEW]
│   └── pytorch_backend.py      # PyTorch model backend [NEW]
│
├── protocols/
│   ├── storage.py              # StorageBackend protocol
│   ├── hitl.py                 # HITLHandler protocol
│   └── models.py               # Data models (HITLRequest, CheckpointEntry, etc.)
│
├── adapters/
│   ├── memory.py               # MemoryStorage implementation
│   ├── file_storage.py         # FileStorage implementation
│   ├── cli_hitl.py             # CLIHITLHandler implementation
│   └── mcp.py                  # MCP server adapter
│
├── testing/
│   ├── gherkin_parser.py       # Parse Gherkin to Pydantic models
│   ├── models.py               # Test result models
│   ├── context.py              # Test execution context
│   ├── test_runner.py          # Parallel test execution
│   ├── evaluation_runner.py    # Multi-run consistency evaluation
│   ├── behave_integration.py   # Generate .feature files
│   ├── events.py               # Structured log events for IDE
│   ├── mock_dependencies.py    # Mock HTTP, DB, Redis [NEW]
│   ├── mock_registry.py        # Unified mock registry [NEW]
│   ├── mock_hitl.py            # Mock HITL handler
│   └── steps/
│       ├── registry.py         # Step pattern matching
│       ├── builtin.py          # Built-in step library
│       ├── custom.py           # Custom Lua steps
│       └── mock_steps.py       # Gherkin mock configuration steps [NEW]
│
└── cli/
    └── app.py                  # CLI application (Typer)
```

---

## Implementation Roadmap

To align the implementation with the specification:

### Recently Completed (Major Milestones)

#### Durability (All 6 Phases Complete)
1. ✅ **Phase 1: Position-Based Execution Log** - Position-based checkpointing with execution log
2. ✅ **Phase 2: Input/Output/State Syntax** - Breaking change from params/outputs to input/output
3. ✅ **Phase 3: Model Primitive** - ML inference with HTTP/PyTorch backends
4. ✅ **Phase 4: Sub-Procedure Auto-Checkpointing** - Direct function call syntax with checkpoints
5. ✅ **Phase 5: Explicit Checkpoint Primitive** - Global `checkpoint()` function
6. ✅ **Phase 6: Script Mode** - Top-level input/output declarations with implicit main

#### Other Recent Features
7. ✅ **Dependencies (Resource Injection)** - HTTP clients, PostgreSQL, Redis with mocking
8. ✅ **Parameter Enum Validation** - Runtime validation of enum constraints
9. ✅ **Output Schema Validation** - Enhanced validation with enum support and field filtering
10. ✅ **Custom Prompts (Partial)** - Parsing and logging of return/error/status prompts
11. ✅ **Session Filters** - Basic implementation of message history filters
12. ✅ **State Schema Validation** - Runtime validation with defaults and type checking
13. ✅ **BDD Testing Framework** - Comprehensive Gherkin integration with built-in steps
14. ✅ **Pydantic Evaluations** - Multi-run consistency evaluation

**Test Status**: 146/146 pytest + 233/233 behave scenarios passing

### High Priority
1. **Guards** - Add pre-execution validation
2. **Summarization Prompts (Full)** - Complete agent injection for summary generation
3. **Async Procedure Spawning** - `Procedure.spawn()`, `wait()`, `wait_all()`

### Medium Priority
4. **Inline Procedures** - Parse and support `procedures:` section in YAML
5. **Agent `prepare` hook** - Enable `prepared` template namespace
6. **System.alert()** - System-level alert infrastructure
7. **Template variables** - Add `context`, `env`, `output` support
8. **More Model Backends** - BERT, scikit-learn, ONNX, SageMaker

### Low Priority
9. **Lambda Durable Context** - AWS Lambda integration
10. **Advanced CLI commands** - resume-all, watch
11. **Graph primitives** - Tree structure support
12. **Lazy Dependency Loading** - Initialize dependencies on first use
13. **More Resource Types** - S3, MongoDB, message queues

---

## Notes

- This implementation guide reflects the state of the codebase as of the last analysis
- Status indicators:
  - ✅ Fully Implemented
  - ⚠️ Partially Implemented
  - ❌ Not Implemented
- For the most up-to-date specification, see [SPECIFICATION.md](SPECIFICATION.md)
