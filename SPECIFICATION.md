# Procedure DSL Specification v5

## Overview

The Procedure DSL enables defining agentic workflows in a token-efficient, sandboxed Lua language. Components are defined using assignment-based syntax.

**Design Philosophy:**
- **Assignment-based definitions** — `worker = Agent {...}` assigns to variables
- **Variable references** — `tools = {done, search}` uses variables, not strings
- **High-level primitives** — operations like `worker()` (callable agents) hide LLM mechanics
- **Uniform recursion** — a procedure invoked by another procedure works identically to a top-level procedure
- **Human-in-the-loop** — first-class support for human interaction, approval, and oversight
- **Built-in reliability** — retries, validation, and error handling under the hood

**Key Principles:**

1. **Uniform Recursion** — A procedure is a procedure, whether invoked externally or by another procedure. Same input, output, prompts, async capabilities everywhere.

2. **Human-in-the-Loop** — Procedures can request human approval, input, or review. Humans can monitor, intervene, and collaborate with running procedures.

---

## Lua DSL Format (.tac files)

**.tac files** define procedures using Lua DSL. All primitives use assignment-based syntax.

```lua
-- Import built-in tool
local done = require("tactus.tools.done")

-- Or define custom tool
custom_tool = Tool {
    description = "Signal completion of the task",
    input = {
        reason = field.string{required = true, description = "Completion message"}
    },
    function(args)
        return "Done: " .. args.reason
    end
}

-- Agents are defined using assignment
worker = Agent {
    provider = "openai",
    model = "gpt-4o",
    system_prompt = "You are a helpful assistant",
    tools = {done}  -- Variable references, not strings
}

-- Procedure (unnamed, defaults to "main")
Procedure {
    -- Input (using field builder syntax)
    input = {
        task = field.string{required = true, description = "The task to perform"},
        max_iterations = field.number{default = 10, description = "Maximum iterations allowed"}
    },

    -- Output (using field builder syntax)
    output = {
        result = field.string{required = true, description = "The result of the task"},
        success = field.boolean{required = true, description = "Whether the task succeeded"}
    },

    -- State is optional, omitted here since not used

    function(input)
        -- Procedure logic here
        local task = input.task
        Log.info("Starting task", {task = task})

        repeat
            worker()  -- Direct callable syntax
        until done.called() or Iterations.exceeded(input.max_iterations)

        return {
            result = "Task completed",
            success = true
        }
    end
}

-- BDD Specifications (optional)
Specification([[
Feature: Task Processing
  Scenario: Task completes successfully
    Given the procedure has started
    When the procedure runs
    Then the done tool should be called
    And the procedure should complete successfully
]])
```

**Key structure:**
- **Tools** defined as `name = Tool {...}` or imported via `require()` like `local done = require("tactus.tools.done")`
- **Agents** defined as `name = Agent {...}` with `tools = {...}`; `tools = {...}` is reserved for inline tool definitions only
- **Procedure { }** unnamed, defaults to "main"
  - Config fields: `input`, `output`, `state` (state is optional)
  - Function as the last element containing the procedure logic
- **Agent calls** use callable syntax: `worker()` or `worker({message = "..."})`
- **Specification()** / **Specifications()** at top level for BDD tests

---

## Input

Input schema defines what the procedure accepts. Validated before execution.

### Field Builder Syntax (Recommended)

```lua
Procedure {
    input = {
        -- Required fields
        topic = field.string{required = true, description = "The topic to research"},

        -- Optional fields with defaults
        depth = field.string{default = "shallow", description = "Research depth"},
        max_results = field.number{default = 10, description = "Maximum number of results"},
        include_sources = field.boolean{default = true, description = "Whether to include sources"},
        tags = field.array{description = "Tags to filter results"},
        config = field.object{description = "Advanced configuration options"}
    },

    function(input)
        -- Access input
        local topic = input.topic
        local depth = input.depth

        -- Arrays are converted to 1-indexed Lua tables
        for i, tag in ipairs(input.tags or {}) do
            Log.info("Tag " .. i .. ": " .. tag)
        end

        -- Objects work as Lua tables
        if input.config and input.config.verbose then
            Log.info("Verbose mode enabled")
        end
    end
}
```

### Alternative Verbose Syntax

An alternative verbose syntax can be used when more explicit configuration is needed:

```lua
Procedure {
    input = {
        topic = field.string{
            required = true,
            description = "The topic to research"
        },
        max_results = field.number{
            default = 10,
            description = "Maximum number of results"
        }
    },
    -- ...
}
```

### Field Builder Functions

**Field types available:**
- `field.string{...}` - String field
- `field.number{...}` - Number field (floats)
- `field.integer{...}` - Integer field
- `field.boolean{...}` - Boolean field
- `field.array{...}` - Array field
- `field.object{...}` - Object field

**Common options:**
- `required = true` - Makes the field required
- `default = value` - Sets a default value (makes field optional)
- `description = "text"` - Describes the field's purpose

**Input Sources:**

1. **CLI Parameters**: Pass inputs via `--param key=value`
   - Arrays: `--param items='[1,2,3]'` or `--param tags="a,b,c"`
   - Objects: `--param config='{"key":"value"}'`
   - Booleans: `--param enabled=true`
   - Numbers: `--param count=5`

2. **Interactive CLI**: Use `--interactive` flag or let CLI prompt for missing required inputs
   - Shows all inputs in a table with types, descriptions, and defaults
   - Allows confirmation or modification of each value
   - Type-appropriate prompts (boolean yes/no, enum selection, JSON for arrays/objects)

3. **GUI Modal**: Automatic form generation before procedure execution
   - Text inputs for strings
   - Number inputs for numbers
   - Checkboxes for booleans
   - Textareas for arrays/objects (JSON format)
   - Dropdowns for enums

4. **SDK**: Pass via `context` parameter to `runtime.execute(source, context)`

**Data Type Conversion:**

- Python lists → Lua tables (1-indexed)
- Python dicts → Lua tables
- Nested structures are recursively converted
- Lua code can use standard table operations (`#array`, `ipairs()`, `pairs()`)

Input values are accessed in templates as `{input.topic}` and in Lua as `input.topic`.

---

## Output

Output schema defines what the procedure returns. Validated after execution.

### Field Builder Syntax (Recommended)

```lua
Procedure {
    output = {
        -- Required fields
        findings = field.string{required = true, description = "Research findings summary"},
        confidence = field.string{required = true, description = "Confidence level"},

        -- Optional fields
        sources = field.array{description = "Source references"}
    },

    function(input)
        -- Procedure logic
        return {
            findings = "...",
            confidence = "high",
            sources = {...}
        }
    end
}
```

When `output` is present:
1. Required fields are validated to exist
2. Types are checked
3. Only declared fields are returned (internal data stripped)

When `output` is omitted, the procedure can return anything without validation.

---

## Message History Configuration

Message history configuration controls how conversation history is managed across agents.

**Aligned with pydantic-ai:** This maps directly to pydantic-ai's `message_history` parameter that gets passed to `agent.run_sync(message_history=...)`.

**Lua DSL format (.tac):**

```lua
Procedure {
    message_history = {
        mode = "isolated",  -- or "shared"
        max_tokens = 120000,
        filter = filters.last_n(50)
    },

    function(input)
        -- Access message history via MessageHistory primitive
        MessageHistory.inject_system("Context for next turn")
        local history = MessageHistory.get()
    end
}
```

**Message history modes:**
- `isolated` (default): Each agent has its own conversation history
- `shared`: All agents share a common conversation history

**Message history filters:**
- `filters.last_n(n)` - Keep only last N messages
- `filters.first_n(n)` - Keep only first N messages
- `filters.token_budget(max)` - Keep messages within token budget
- `filters.head_tokens(max)` - Keep earliest messages within token budget
- `filters.tail_tokens(max)` - Keep latest messages within token budget
- `filters.by_role(role)` - Filter by message role
- `filters.system_prefix()` - Keep leading system messages
- `filters.compose(...)` - Combine multiple filters

**MessageHistory transforms:**
Use the `MessageHistory` primitive to inspect and mutate history from within procedures.

- `MessageHistory.reset({keep = "system_prefix" | "system_all" | "none"})`
- `MessageHistory.head(n)` / `MessageHistory.tail(n)` - Non-mutating views
- `MessageHistory.slice({start = i, stop = j})` - 1-based slice view
- `MessageHistory.keep_head(n)` / `MessageHistory.keep_tail(n)` - Mutating trims
- `MessageHistory.tail_tokens(max_tokens)` / `MessageHistory.keep_tail_tokens(max_tokens)`
- `MessageHistory.rewind(n)` - Remove last N messages
- `MessageHistory.checkpoint(name?) -> id`
- `MessageHistory.rewind_to(id_or_name)`

**Token budgeting:** token-based filters and transforms use a deterministic heuristic
(~4 characters per token) unless a model-specific tokenizer is added in the future.

**Agent-level overrides:**

Agents can override procedure-level message history settings:

```lua
local done = require("tactus.tools.done")

researcher = Agent {
    provider = "openai",
    model = "gpt-4o",
    system_prompt = "Research the topic",
    tools = {"brave_search", "done"},  -- MCP tools referenced by name

    message_history = {
        source = "shared",  -- Use shared history
        filter = filters.compose(
            filters.token_budget(80000),
            filters.last_n(20)
        )
    }
}
```

---

## Structured Output (output_type)

Agents can enforce structured output schemas using `output_type`, aligned with pydantic-ai's validation and automatic retry.

**Lua DSL format (.tac):**

```lua
local done = require("tactus.tools.done")

extractor = Agent {
    provider = "openai",
    model = "gpt-4o",
    system_prompt = "Extract structured data from user input",
    tools = {done},

    -- Define structured output schema (aligned with pydantic-ai's output_type)
    output = {
        name = field.string{required = true},
        age = field.number{required = true},
        email = field.string{}
    }
}
```

**Supported types:**
- `string` / `str` - Text data
- `number` / `float` - Floating point numbers
- `integer` / `int` - Whole numbers
- `boolean` / `bool` - True/false values
- `object` / `dict` - Nested objects
- `array` / `list` - Lists of items

**Validation behavior:**

When `output_type` is specified, pydantic-ai automatically:
1. Validates the LLM's response against the schema
2. Retries if the response doesn't match the schema
3. Provides error feedback to the LLM for correction

This ensures type-safe, structured outputs from agents.

---

## Result Object

`agent()` (callable agent) returns a `Result` object (not raw data) with access to response data, token usage, and conversation history.

**Aligned with pydantic-ai:** The Result object wraps pydantic-ai's `RunResult` and provides Lua-accessible properties.

**Properties:**
- `result.value` - The response value (string or structured data)
- `result.usage` - Token usage stats (prompt_tokens, completion_tokens, total_tokens)

**Methods:**
- `result.cost()` - Cost statistics (total_cost, prompt_cost, completion_cost)

**Example:**

```lua
worker = Agent {
    provider = "openai",
    model = "gpt-4o",
    system_prompt = "You are helpful"
}

Procedure {
    function(input)
        local result = worker()

        -- Access response value
        Log.info("Response", {value = result.value})

        -- Access token usage
        Log.info("Tokens used", {
            prompt = result.usage.prompt_tokens,
            completion = result.usage.completion_tokens,
            total = result.usage.total_tokens
        })

    end
}
```

**With structured output:**

```lua
extractor = Agent {
    provider = "openai",
    model = "gpt-4o",
    output = {
        city = field.string{required = true},
        country = field.string{required = true}
    }
}

Procedure {
    function(input)
        local result = extractor()

        -- Access structured data fields
        Log.info("Extracted", {
            city = result.value.city,
            country = result.value.country
        })
    end
}
```

---

## Summarization Prompts

These prompts control how the procedure communicates its results:

### `return_prompt:`

Injected when the procedure completes successfully. The agent does one final turn to generate a summary, which becomes the return value.

```lua
Procedure {
    return_prompt = [[
Summarize your work:
- What was accomplished
- Key findings or results
- Any important notes for the caller
    ]],
    -- rest of procedure...
}
```

### `error_prompt:`

Injected when the procedure fails (exception or max iterations exceeded). The agent explains what went wrong.

```lua
Procedure {
    error_prompt = [[
The task could not be completed. Explain:
- What you were attempting
- What went wrong
- Any partial progress made
    ]],
    -- rest of procedure...
}
```

### `status_prompt:`

Injected when a caller requests a status update (async procedures only). The agent reports current progress without stopping.

```lua
Procedure {
    status_prompt = [[
Provide a brief progress update:
- What has been completed
- What you're currently working on
- Estimated remaining work
    ]],
    -- rest of procedure...
}
```

### Defaults

If not specified, the following defaults are used:

```lua
-- Default return_prompt:
"Summarize the result of your work concisely."

-- Default error_prompt:
"Explain what went wrong and any partial progress made."

-- Default status_prompt:
"Briefly describe your current progress and remaining work."
```

---

## Async and Recursion Settings

```lua
Procedure {
    -- Enable async invocation (caller can spawn and continue)
    async = true,

    -- Maximum recursion depth (prevents infinite recursion)
    max_depth = 5,

    -- Maximum turns for this procedure
    max_turns = 50,

    -- Checkpoint interval for recovery (async only)
    checkpoint_interval = 10,

    -- rest of procedure...
}
```

---

## Execution Contexts

Procedures run identically in two execution contexts:

### Local Execution Context

For development and simple deployments:

- Checkpoints stored in database (ChatMessage with metadata)
- HITL waits create `PENDING_*` messages and exit
- Resume via polling loop or manual trigger
- Same procedure code, no changes needed

### Lambda Durable Execution Context

For production deployments on AWS:

- Uses AWS Lambda Durable Functions SDK
- Native checkpoint/replay mechanism
- HITL waits use Lambda callbacks (zero compute cost while waiting)
- Automatic retry with configurable backoff
- Executions can span up to 1 year

### Abstraction Layer

The runtime provides an `ExecutionContext` that abstracts over both backends:

```
┌─────────────────────────────────────────────┐
│           Procedure DSL (Lua)               │
│  worker() / Human.approve() / etc.          │
└─────────────────────┬───────────────────────┘
                      │
          ┌───────────┴───────────┐
          │   ExecutionContext    │
          │      (Protocol)       │
          └───────────┬───────────┘
                      │
        ┌─────────────┴─────────────┐
        ▼                           ▼
┌───────────────────┐     ┌───────────────────┐
│ LocalExecution    │     │ DurableExecution  │
│ Context           │     │ Context           │
├───────────────────┤     ├───────────────────┤
│ - DB checkpoints  │     │ - Lambda SDK      │
│ - Manual resume   │     │ - Native suspend  │
│ - Polling loop    │     │ - Callback API    │
└───────────────────┘     └───────────────────┘
```

### Primitive Mapping

| DSL Primitive | Local Context | Lambda Durable Context |
|---------------|---------------|------------------------|
| `worker()` | DB checkpoint before/after | `context.step()` |
| `Human.approve()` | Create PENDING_*, exit, await RESPONSE | `context.create_callback()` + `callback.result()` |
| `Human.input()` | Create PENDING_*, exit, await RESPONSE | `context.create_callback()` + `callback.result()` |
| `Human.review()` | Create PENDING_*, exit, await RESPONSE | `context.create_callback()` + `callback.result()` |
| `Sleep(seconds)` | DB checkpoint, exit, resume after delay | `context.wait(Duration.from_seconds(n))` |
| `Procedure.spawn()` | Create child procedure record | `context.run_in_child_context()` |

### HITL Response Flow

**Local Context:**
```
1. Human.approve() called
2. Create ChatMessage with humanInteraction: PENDING_APPROVAL
3. Save Lua coroutine state to procedure metadata
4. Exit procedure (return control to runner)
5. [Human responds in UI → creates RESPONSE message]
6. Resume loop detects RESPONSE, reruns procedure
7. Procedure replays, Human.approve() returns the response value
```

**Lambda Durable Context:**
```
1. Human.approve() called
2. context.create_callback() → gets callback_id
3. Create ChatMessage with humanInteraction: PENDING_APPROVAL, callback_id in metadata
4. callback.result() suspends Lambda (zero cost)
5. [Human responds in UI → calls SendDurableExecutionCallbackSuccess API]
6. Lambda resumes automatically
7. callback.result() returns the response value
```

### Writing Portable Procedures

Procedures are automatically portable. The runtime handles the abstraction:

```lua
-- This works identically in both contexts
local approved = Human.approve({
  message = "Deploy to production?",
  timeout = 3600,
  default = false
})

if approved then
  deploy()
end
```

No conditional logic needed. The execution context handles:
- How to persist the pending request
- How to suspend execution
- How to resume when response arrives
- How to return the value to the Lua code

---

## Guards

Validation that runs before the procedure executes:

```lua
Procedure {
    guards = {
        function(input)
            if not File.exists(input.file_path) then
                return false, "File not found: " .. input.file_path
            end
            return true
        end,
        function(input)
            if input.depth > 10 then
                return false, "Depth cannot exceed 10"
            end
            return true
        end
    },
    -- rest of procedure...
}
```

Guards return `true` to proceed or `false, "error message"` to abort.

---

## Dependencies

Tactus supports declaring external resource dependencies (HTTP clients, databases, caches) that are automatically initialized and injected into your procedure.

### Resource Dependencies

Declare resources your procedure needs (HTTP APIs, databases, caches, etc.):

```lua
Procedure {
    input = {
        city = field.string{required = true}
    },

    -- Declare resource dependencies
    dependencies = {
        weather_api = field.http_client{
            base_url = "https://api.weather.com",
            headers = {
                ["Authorization"] = env.WEATHER_API_KEY
            },
            timeout = 30.0
        },
        database = {
            type = "postgres",
            connection_string = env.DATABASE_URL,
            pool_size = 10
        },
        cache = {
            type = "redis",
            url = env.REDIS_URL
        }
    },

    function(input)
        -- Dependencies are automatically created and available
        -- Tools (via MCP) can access them through the dependency injection system
        worker()
        return {result = "done"}
    end
}
```

**Supported Resource Types:**
- `http_client` - HTTP client for API calls (backed by httpx.AsyncClient)
- `postgres` - PostgreSQL connection pool (backed by asyncpg)
- `redis` - Redis client (backed by redis.asyncio)

**Benefits:**
- **Lifecycle Management:** Resources are automatically created at procedure start and cleaned up on exit
- **Connection Pooling:** HTTP clients and database connections are reused across tool calls
- **Configuration:** Centralized dependency configuration in procedure declaration
- **Testing:** Easy to mock dependencies for fast unit tests

### Tool and Procedure Dependencies

Tools and procedures are defined as variables and used directly:

```lua
-- Define sub-procedure
researcher = Procedure {
    name = "researcher",
    -- MCP tools would be referenced in toolsets
    -- ...
}

-- Main procedure uses procedures directly
Procedure {
    function(input)
        -- Procedures are accessed as variables
        researcher.run({query = input.query})
        return {result = "done"}
    end
}
```

If a required variable is undefined, Lua raises an error immediately.

### Testing with Dependencies

#### Unit Tests (Mocked Dependencies)

Run tests with automatically mocked dependencies for fast, deterministic tests:

```bash
tactus test procedure.tac --mocked
```

Mock responses can be configured in Gherkin steps:

```gherkin
Feature: Weather Lookup
  Scenario: Successful lookup
    Given the weather_api returns '{"temp": 72, "condition": "sunny"}'
    When the Worker agent takes turn
    Then the done tool should be called
```

**Mock Configuration Steps:**

HTTP Dependencies:
- `Given the {dep_name} returns '{response}'` - Default response for any path
- `Given the {dep_name} returns '{response}' for {path}` - Response for specific path
- `Given the {dep_name} returns '{response}' with status {code}` - Response with status code

HITL (Human-in-the-Loop):
- `Given Human.approve will return true` - Mock approval requests
- `Given Human.input will return 'value'` - Mock input requests
- `Given when asked "message" return true` - Mock specific message

Assertions:
- `Then the {dep_name} should have been called` - Verify dependency was used
- `Then the {dep_name} should not have been called` - Verify dependency wasn't used
- `Then the {dep_name} should have been called {n} times` - Verify call count

#### Integration Tests (Real Dependencies)

Run tests with real external services:

```bash
tactus test procedure.tac --integration
```

This creates real HTTP clients, database connections, etc., allowing you to validate end-to-end behavior.

### Dependency Injection Details

When you declare dependencies:

1. **Runtime Initialization:** The runtime creates resource instances (HTTP clients, DB pools, etc.) based on your configuration

2. **Agent Injection:** Dependencies are injected into agents via an expanded `AgentDeps` class:

```python
@dataclass
class GeneratedAgentDeps(AgentDeps):
    # Framework dependencies
    state_primitive: Any
    context: Dict[str, Any]
    system_prompt_template: str

    # Your declared dependencies
    weather_api: httpx.AsyncClient
    database: asyncpg.Pool
    cache: redis.asyncio.Redis
```

3. **Tool Access:** Tools (Python functions decorated with `@agent.tool`) receive dependencies via `RunContext[Deps]`:

```python
@agent.tool
async def get_weather(ctx: RunContext[GeneratedAgentDeps], city: str) -> str:
    # Access dependency
    response = await ctx.deps.weather_api.get(f"/weather?city={city}")
    return response.text
```

4. **Cleanup:** Resources are automatically closed when the procedure completes or fails

### Nested Procedures and Dependencies

Child procedures inherit parent dependencies:

```lua
-- Parent procedure
Procedure {
    dependencies = {
        api_client = {type = "http_client", base_url = "https://api.example.com"}
    },
    function(input)
        -- Child procedure uses same api_client instance
        local child_result = Procedure("child")({...})
    end
}
```

Both parent and child use the same HTTP client instance, enabling efficient connection reuse.

### Checkpoint and Restart

Dependencies are **recreated** on procedure restart (after checkpoint). The dependency configuration is saved, but instances themselves are ephemeral per execution session.

---

## Template Variable Namespaces

| Namespace | Source | Example |
|-----------|--------|---------|
| `input` | Input parameters | `{input.topic}` |
| `output` | (In return_prompt) Final values | `{output.findings}` |
| `context` | Runtime context from caller | `{context.parent_id}` |
| `state` | Mutable procedure state | `{state.items_processed}` |
| `prepared` | Output of agent's `prepare` hook | `{prepared.file_contents}` |
| `env` | Environment variables | `{env.API_KEY}` |

Templates are re-evaluated before each agent turn.

---

## Human-in-the-Loop (HITL)

Procedures can interact with human operators for approval, input, review, or notification.

### Message Classification

Every chat message has a `humanInteraction` classification that determines visibility and behavior:

| Value | Description | Blocks? | Response Expected? |
|-------|-------------|---------|-------------------|
| `INTERNAL` | Agent-only, hidden from human UI | No | No |
| `CHAT` | Normal human-AI conversation | No | Optional |
| `CHAT_ASSISTANT` | AI response in conversation | No | No |
| `NOTIFICATION` | FYI from procedure to human | No | No |
| `ALERT_INFO` | System info alert | No | No |
| `ALERT_WARNING` | System warning alert | No | No |
| `ALERT_ERROR` | System error alert | No | No |
| `ALERT_CRITICAL` | System critical alert | No | No |
| `PENDING_APPROVAL` | Waiting for yes/no | Yes | Yes |
| `PENDING_INPUT` | Waiting for free-form input | Yes | Yes |
| `PENDING_REVIEW` | Waiting for human review | Yes | Yes |
| `RESPONSE` | Human's response to pending request | No | No |
| `TIMED_OUT` | Request expired without response | No | No |
| `CANCELLED` | Request was cancelled | No | No |

**Usage patterns:**

- **Procedure internals:** `INTERNAL` — LLM reasoning, tool calls, intermediate steps
- **Human-AI chat:** `CHAT` / `CHAT_ASSISTANT` — conversational assistants
- **Procedure notifications:** `NOTIFICATION` — progress updates from workflows
- **System monitoring:** `ALERT_*` — devops alerts, resource warnings, errors
- **Interactive requests:** `PENDING_*` — approval gates, input requests, reviews

### HITL Primitives

#### Approval (Blocking)

Request yes/no approval from a human:

```lua
local approved = Human.approve({
  message = "Should I proceed with this operation?",
  context = operation_details,  -- Any table of relevant data for the human
  timeout = 3600,  -- seconds, nil = wait forever
  default = false  -- return value if timeout
})

if approved then
  perform_operation()
else
  Log.info("Operation cancelled by operator")
end
```

The `context` parameter accepts any table and is displayed to the human in the approval UI:

```lua
-- Example contexts
context = {action = "deploy", environment = "production", version = "2.1.0"}
context = {query = sql_statement, affected_rows = row_count}
context = {amount = transfer_amount, recipient = account_id}
```

#### Input (Blocking)

Request free-form input from a human:

```lua
local response = Human.input({
  message = "What topic should I research next?",
  placeholder = "Enter a topic...",  -- UI hint
  timeout = nil  -- wait forever
})

if response then
  Procedure.run("researcher", {topic = response})
else
  Log.warn("No input received, using default")
end
```

#### Review (Blocking)

Request human review of a work product:

```lua
local review = Human.review({
  message = "Please review this generated content",
  artifact = generated_content,
  artifact_type = "document",  -- document, code, config, score_promotion, etc.
  options = {
    {label = "Approve", type = "action"},
    {label = "Reject", type = "cancel"},
    {label = "Revise", type = "action"}
  },
  timeout = 86400  -- 24 hours
})

if review.decision == "Approve" then
  publish(generated_content)
elseif review.decision == "Revise" then
  -- Human provided feedback, retry with their input
  state.human_feedback = review.feedback
else  -- "Reject"
  Log.warn("Content rejected", {feedback = review.feedback})
end
```

**Options format:**

Each option is a hash with at least a `label` key. The label becomes `review.decision`:

```lua
options = {
  {label = "Approve", type = "action"},     -- Primary action button
  {label = "Reject", type = "cancel"},      -- Cancel/destructive button  
  {label = "Request Changes", type = "action"}
}
-- review.decision will be "Approve", "Reject", or "Request Changes"
```

Additional keys can be added as needed for UI rendering.

**Response fields:**

```lua
review.decision        -- The label of the selected option
review.feedback        -- Optional text feedback from human
review.edited_artifact -- Optional: human's edited version of artifact
review.responded_at    -- ISO timestamp when human responded
```

Note: We don't track responder identity since users aren't first-class records in the schema.

#### Notification (Non-Blocking)

Send information to human without waiting:

```lua
Human.notify({
  message = "Starting phase 2: data processing",
  level = "info"  -- info, warning, error
})

Human.notify({
  message = "Found anomalies that may need attention",
  level = "warning",
  context = {
    anomaly_count = #anomalies,
    details = anomaly_summary
  }
})
```

#### Alert (Non-Blocking, System-Level)

Send system/devops alerts. Unlike other HITL primitives, alerts can be sent programmatically from anywhere—not just from within procedure workflows:

```lua
-- From within a procedure
System.alert({
  message = "Procedure exceeded memory threshold",
  level = "warning",  -- info, warning, error, critical
  source = "batch_processor",
  context = {
    procedure_id = context.procedure_id,
    memory_mb = current_memory,
    threshold_mb = memory_threshold
  }
})
```

```python
# From Python monitoring code (outside any procedure)
create_chat_message(
    session_id=monitoring_session_id,
    role="SYSTEM",
    content="Database connection pool exhausted",
    human_interaction="ALERT_ERROR",
    metadata={
        "source": "db_monitor",
        "pool_size": 100,
        "waiting_connections": 47
    }
)
```

Alert levels map to `humanInteraction` values:

| Level | humanInteraction |
|-------|------------------|
| `info` | `ALERT_INFO` |
| `warning` | `ALERT_WARNING` |
| `error` | `ALERT_ERROR` |
| `critical` | `ALERT_CRITICAL` |

This enables unified alert dashboards that show both AI procedure alerts and traditional system monitoring alerts in the same interface.

#### Escalation (Blocking)

Hand off to human entirely:

```lua
Human.escalate({
  message = "Unable to resolve this automatically",
  context = {
    attempts = state.resolution_attempts,
    last_error = last_error,
    current_state = State.all()
  }
})
-- Procedure pauses until human resolves and resumes
```

### Declarative HITL Points

For predictable workflows, declare interaction points in Lua:

```lua
Procedure {
    hitl = {
        review_draft = {
            type = "review",
            message = "Please review the generated document",
            timeout = 86400,
            options = {"approve", "edit", "reject"}
        },

        confirm_publish = {
            type = "approval",
            message = "Publish this document to production?",
            timeout = 3600,
            default = false
        },

        get_topic = {
            type = "input",
            message = "What topic should be researched?",
            placeholder = "Enter topic..."
        }
    },

    function(input)
        -- Uses the declared configuration
        local review = Human.review("review_draft", {artifact = draft})
        local approved = Human.approve("confirm_publish")
        local topic = Human.input("get_topic")

        -- rest of procedure...
    end
}
```

### Timeout Handling

```lua
local approved, timed_out = Human.approve({
  message = "Proceed?",
  timeout = 3600
})

if timed_out then
  Log.warn("Approval timed out, using default")
  -- approved contains the default value
end
```

Or with explicit timeout behavior:

```lua
local result = Human.approve({
  message = "Proceed?",
  timeout = 3600,
  on_timeout = "error"  -- "default", "error", or "retry"
})
-- If on_timeout = "error", throws exception on timeout
```

## Human-AI Chat (Non-Procedural)

The same `ChatSession` and `ChatMessage` infrastructure supports regular conversational AI assistants that aren't running procedure workflows.

### Chat Assistant Pattern

For interactive AI assistants (help bots, Q&A systems, general chat):

```
ChatSession:
  category: "assistant"
  status: ACTIVE
  
ChatMessage (human):
  role: USER
  humanInteraction: CHAT
  content: "How do I reset my password?"
  
ChatMessage (AI):
  role: ASSISTANT
  humanInteraction: CHAT_ASSISTANT
  content: "You can reset your password by..."
```

Key differences from procedure workflows:

- No `procedureId` on the session (or links to a simple non-workflow procedure)
- Messages use `CHAT` / `CHAT_ASSISTANT` visibility by default
- No stages, no workflow orchestration
- Simple request-response or multi-turn conversation

### Hybrid: Chat with Procedure Invocation

A chat assistant can invoke procedures on behalf of the user:

```
User (CHAT): "Generate a report on Q3 sales"

Assistant (CHAT_ASSISTANT): "I'll generate that report for you..."

-- Assistant spawns a procedure, which creates INTERNAL messages
-- When complete, assistant responds:

Assistant (CHAT_ASSISTANT): "Here's your Q3 sales report: [link]"
```

The procedure's internal messages stay `INTERNAL` while the chat remains natural.

---

## Script Mode (Zero-Wrapper Syntax)

For simple procedures, you can write code directly without the `Procedure {}` wrapper. This "zero-wrapper" script mode is automatically detected when you have top-level `input {}` or `output {}` declarations without an explicit `Procedure {}` block.

### Basic Example

```lua
-- Script mode: no Procedure wrapper needed
input {
    name = field.string{required = true, description = "Name to greet"}
}

output {
    greeting = field.string{required = true, description = "Greeting message"}
}

-- Just write code directly
local message = "Hello, " .. input.name .. "!"

return {greeting = message}
```

**What happens:** The runtime automatically transforms this into:

```lua
input { name = field.string{required = true} }
output { greeting = field.string{required = true} }

Procedure {
    function(input)
        local message = "Hello, " .. input.name .. "!"
        return {greeting = message}
    end
}
```

### With Agents

Script mode works seamlessly with agent calls:

```lua
input {
    task = field.string{required = true, description = "Task to complete"}
}

output {
    result = field.string{required = true, description = "Completion result"}
}

-- Mock configuration (optional, for testing)
Mocks {
    worker = {
        returns = {
            response = "Task completed successfully!",
            tool_calls = "done"
        }
    }
}

-- Define tools and agents as usual
local done = require("tactus.tools.done")

worker = Agent {
    provider = "openai",
    model = "gpt-4o",
    system_prompt = "Complete the given task efficiently",
    tools = {done}
}

-- Executable code (agent calls, control flow, returns)
worker({message = input.task})

if done.called() then
    return {result = "Success: " .. done.last_call().args.reason}
else
    return {result = "Agent did not complete"}
end
```

### With State

State management works in script mode:

```lua
input {
    value = field.number{required = true}
}

output {
    doubled = field.number{required = true},
    original = field.number{required = true}
}

-- State assignment
state.original = input.value
state.result = state.original * 2

return {
    doubled = state.result,
    original = state.original
}
```

### Detection

A file is automatically treated as script mode when:

1. **Has top-level `input {}` or `output {}` declarations**, AND
2. **Does NOT have explicit `Procedure {}` or named procedure**

If you include an explicit `Procedure {}`, script mode transformation is skipped.

### How It Works

The runtime detects script mode during execution and performs source transformation:

1. **Splits the source** into declarations (Agent, Tool, Mocks, input, output, etc.) and executable code (agent calls, return statements, control flow)
2. **Wraps executable code** in an implicit `Procedure {}` function
3. **Merges schemas** from top-level `input {}` and `output {}` into the implicit procedure
4. **Executes normally** using the standard procedure execution flow

### Transformation Rules

**Declarations** (stay at top level):
- `input {}`
- `output {}`
- `Mocks {}`
- `Specification()` / `Specifications()`
- Agent definitions: `name = Agent {}`
- Tool definitions: `name = Tool {}` or imported via `require()` like `local done = require("tactus.tools.done")`
- Model definitions: `name = Model {}`
- Comments and blank lines

**Executable code** (wrapped in Procedure function):
- Local variable assignments: `local x = ...`
- Agent calls: `worker()` or `worker({...})`
- State assignments: `state.x = ...`
- Control flow: `if`, `while`, `for`, `repeat`
- Return statements: `return {...}`
- Any other function calls

### When to Use Script Mode

**Use script mode for:**
- Simple, single-purpose procedures
- Quick prototypes and experiments
- Linear workflows without complex sub-procedures
- Examples and tutorials

**Use explicit `Procedure {}` for:**
- Complex procedures with multiple sub-procedures
- When you need explicit procedure configuration
- Procedures that will grow in complexity
- Better IDE support and syntax highlighting

### Migration

Script mode files can be converted to explicit procedures without breaking:

```lua
-- Before (script mode)
input { name = field.string{required = true} }
output { greeting = field.string{required = true} }

local msg = "Hello, " .. input.name
return {greeting = msg}
```

```lua
-- After (explicit procedure)
Procedure {
    input = { name = field.string{required = true} },
    output = { greeting = field.string{required = true} },

    function(input)
        local msg = "Hello, " .. input.name
        return {greeting = msg}
    end
}
```

---

## Inline Procedure Definitions

For convenience, sub-procedures can be defined and called within a main procedure:

```lua
-- Define tools
local done = require("tactus.tools.done")

-- Sub-procedure defined at top level
researcher = Procedure {
    name = "researcher",  -- Named sub-procedure
    description = "Researches a topic",

    input = {
        query = field.string{required = true}
    },

    output = {
        findings = field.string{required = true}
    },

    return_prompt = "Summarize your research findings.",

    function(input)
        -- Define agent inline or reference a top-level agent
        repeat
            worker()
        until done.called()

        return {findings = "Research complete"}
    end
}

-- Main procedure that uses the sub-procedure
Procedure {
    function(input)
        -- Call sub-procedure (variable reference)
        local result = researcher.run({query = "quantum computing"})

        -- Use the result
        Log.info("Research findings", {findings = result.findings})

        return {result = "Coordination complete"}
    end
}
```

Sub-procedures follow the **exact same structure** as top-level procedures.

---

## Agent Definitions

Agents are the cognitive workers within a procedure. Defined using assignment-based syntax:

```lua
local done = require("tactus.tools.done")

worker = Agent {
    provider = "openai",
    model = "gpt-4o",

    prepare = function()
        return {
            current_time = os.date(),
            data = load_context_data()
        }
    end,

    system_prompt = [[
You are processing: {input.task}
Context: {prepared.data}
    ]],

    initial_message = "Begin working on the task.",

    tools = {"brave_search_search", "done"},  -- MCP tools referenced by string name

    filter = {
        class = "ComposedFilter",
        chain = {
            {class = "TokenBudget", max_tokens = 120000},
            {class = "LimitToolResults", count = 2}
        }
    },

    response = {
        retries = 3,
        retry_delay = 1.0
    },

    max_turns = 50
}
```

When you define `worker = Agent {...}`, invoke it directly: `worker()` or `worker({message = "..."})` for callable syntax.

### Model Configuration

Agents can specify which LLM model to use and configure model-specific parameters. The `model` field accepts either a simple string or a dictionary with settings.

**Simple string format** (for default settings):

```lua
local done = require("tactus.tools.done")

greeter = Agent {
    provider = "openai",
    model = "gpt-4o-mini",
    system_prompt = "You are a friendly greeter.",
    tools = {done}
}
```

**Dictionary format** (with custom settings):

```lua
local done = require("tactus.tools.done")

creative_writer = Agent {
    provider = "openai",
    model = {
        name = "gpt-4o",
        temperature = 0.9,
        top_p = 0.95,
        max_tokens = 2000
    },
    system_prompt = "You are a creative writer.",
    tools = {done}
}
```

**Available model settings:**

- **Standard parameters** (GPT-4 models):
  - `temperature` (0.0-2.0): Controls randomness
  - `top_p` (0.0-1.0): Nucleus sampling threshold
  - `max_tokens`: Maximum tokens in response
  - `presence_penalty`: Penalize repeated topics
  - `frequency_penalty`: Penalize repeated tokens
  - `seed`: For reproducible outputs
  - `parallel_tool_calls`: Enable parallel tool execution

- **Reasoning models** (o1, GPT-5):
  - `openai_reasoning_effort`: `'low'`, `'medium'`, or `'high'`
  - `max_tokens`: Maximum tokens in response
  - Note: `temperature` and `top_p` are not supported on reasoning models

**Example with multiple agents using different models:**

```lua
local done = require("tactus.tools.done")

analyst = Agent {
    provider = "openai",
    model = {
        name = "gpt-5",
        openai_reasoning_effort = "high",
        max_tokens = 4000
    },
    system_prompt = "Analyze the data carefully.",
    tools = {done}
}

summarizer = Agent {
    provider = "openai",
    model = {
        name = "gpt-4o-mini",
        temperature = 0.3,
        max_tokens = 500
    },
    system_prompt = "Summarize concisely.",
    tools = {done}
}
```

**Provider specification:**

**IMPORTANT:** Every agent must specify a `provider` (either directly on the agent or via `default_provider` at the procedure level). Supported providers are `openai` and `bedrock`.

```lua
local done = require("tactus.tools.done")

openai_agent = Agent {
    provider = "openai",
    model = "gpt-4o",
    system_prompt = "You are a helpful assistant.",
    tools = {done}
}

bedrock_agent = Agent {
    provider = "bedrock",
    model = "anthropic.claude-3-5-sonnet-20240620-v1:0",
    system_prompt = "You are a helpful assistant.",
    tools = {done}
}
```

**Using procedure-level defaults:**

You can set `default_provider` and `default_model` at the procedure level to avoid repeating them:

```lua
local done = require("tactus.tools.done")

worker = Agent {
    -- Uses default_model and default_provider from procedure
    system_prompt = "Process the task.",
    tools = {done}
}

specialist = Agent {
    -- Can override provider/model in agent definition
    model = "gpt-4o",
    system_prompt = "Specialist task.",
    tools = {done}
}

Procedure {
    default_model = "gpt-4o-mini",
    default_provider = "openai",

    function(input)
        worker()     -- Uses defaults
        specialist() -- Uses its own model
    end
}
```

**Mixed providers in one procedure:**

```lua
local done = require("tactus.tools.done")

openai_agent = Agent {
    provider = "openai",
    model = "gpt-4o-mini",
    system_prompt = "Fast processing with OpenAI.",
    tools = {done}
}

bedrock_agent = Agent {
    provider = "bedrock",
    model = "anthropic.claude-3-5-sonnet-20240620-v1:0",
    system_prompt = "Deep analysis with Claude.",
    tools = {done}
}
```

### Module Configuration

Agents can specify which DSPy module strategy to use via the `module` parameter. This controls how prompts are formatted and whether reasoning steps are included.

**Default module** (Predict):

```lua
local done = require("tactus.tools.done")

simple_agent = Agent {
    provider = "openai",
    model = "gpt-4o-mini",
    system_prompt = "You are a helpful assistant.",
    tools = {done}
}
```

**ChainOfThought module** (adds reasoning steps):

```lua
local done = require("tactus.tools.done")

thinking_agent = Agent {
    provider = "openai",
    model = "gpt-4o",
    module = "ChainOfThought",
    system_prompt = "You are a careful analyst.",
    tools = {done}
}
```

**Raw module** (minimal formatting for cost optimization):

```lua
local done = require("tactus.tools.done")

efficient_agent = Agent {
    provider = "openai",
    model = "gpt-4o-mini",
    module = "Raw",
    system_prompt = "You are concise.",
    tools = {done}
}
```

**Available module options:**

- **`"Predict"`** (default): Simple prediction without reasoning traces. Uses DSPy's standard field delimiters (~300-400 characters overhead per call).

- **`"ChainOfThought"`**: Adds step-by-step reasoning before generating the final response. Useful for complex tasks requiring explicit reasoning. Increases token usage due to reasoning output (~500-2000 additional tokens depending on complexity).

- **`"Raw"`**: Minimal formatting with direct LM calls. No DSPy delimiter overhead. Best for simple interactions, cost optimization, or when prompt space is constrained.

**Token overhead comparison:**

For a simple "Hello, World!" interaction:
- **Raw**: 29 tokens total (20 prompt + 9 completion)
- **Predict**: 230 tokens total (210 prompt + 19 completion)
- **Difference**: ~8x more tokens with Predict due to delimiter formatting

**When to use each module:**

- Use **`Raw`** for simple interactions, high-volume API calls, or when minimizing cost is a priority
- Use **`Predict`** when you need structured outputs or are using DSPy's optimization features (bootstrapping, etc.)
- Use **`ChainOfThought`** for complex reasoning tasks where you want to see the agent's thought process

---

## DSPy Integration

Tactus provides first-class support for DSPy modules, enabling declarative machine learning components alongside agentic workflows. DSPy modules define typed signatures and can use various prompting strategies.

### Language Model Configuration

Configure the language model for DSPy modules using `LM()`:

```lua
-- LM uses LiteLLM format: "provider/model-name"
LM("openai/gpt-4o-mini")

-- For reasoning models
LM("openai/gpt-5", {
    model_type = "responses"  -- Required for o3, gpt-5 series
})
```

### Basic Module

Create modules using the `Module` primitive with string signatures:

```lua
-- Simple predict module
qa = Module {
    signature = "question -> answer",
    strategy = "predict"
}

-- Invoke the module
local result = qa({question = "What is the capital of France?"})
print(result.answer)  -- "Paris"
```

### Chain of Thought Strategy

Use `chain_of_thought` for questions requiring reasoning:

```lua
-- CoT adds a 'reasoning' field to the output
reasoning_qa = Module {
    signature = "question -> reasoning, answer",
    strategy = "chain_of_thought"
}

local result = reasoning_qa({
    question = "Who provided the assist for the winning goal in the 2014 World Cup final?"
})
print(result.reasoning)  -- Step-by-step reasoning
print(result.answer)     -- "Andre Schürrle"
```

### Typed Signatures

For complex modules, use `Signature` to define typed input/output:

```lua
outline_generator = Module {
    signature = Signature {
        input = {
            topic = field.string{description = "The topic to outline"},
            depth = field.string{default = "medium", description = "Outline depth"}
        },
        output = {
            outline = field.string{description = "Structured outline"},
            section_titles = field.array{description = "List of sections"}
        }
    },
    strategy = "chain_of_thought"
}
```

### Multi-Module Pipelines

Chain modules to build complex workflows:

```lua
LM("openai/gpt-4o-mini")

-- Step 1: Generate outline
outline_gen = Module {
    signature = "topic -> outline, sections",
    strategy = "chain_of_thought"
}

-- Step 2: Write introduction
intro_writer = Module {
    signature = "topic, outline -> introduction",
    strategy = "predict"
}

-- Step 3: Write conclusion
conclusion_writer = Module {
    signature = "topic, outline, introduction -> conclusion",
    strategy = "chain_of_thought"
}

Procedure {
    function(input)
        local outline = outline_gen({topic = input.topic})
        local intro = intro_writer({
            topic = input.topic,
            outline = outline.outline
        })
        local conclusion = conclusion_writer({
            topic = input.topic,
            outline = outline.outline,
            introduction = intro.introduction
        })
        return {
            outline = outline.outline,
            introduction = intro.introduction,
            conclusion = conclusion.conclusion
        }
    end
}
```

### Available Strategies

- `predict` - Simple input-output prediction
- `chain_of_thought` - Step-by-step reasoning before final answer
- `react` - Reasoning + Action (for tool-using modules)

### Mocking DSPy Modules

Mock modules for testing using the `Mocks {}` primitive:

```lua
Mocks {
    qa = {
        returns = {answer = "Mocked answer"}
    },
    -- Temporal mocks for sequential calls
    reasoning_qa = {
        temporal = {
            {reasoning = "First call...", answer = "First answer"},
            {reasoning = "Second call...", answer = "Second answer"}
        }
    }
}
```

---

## Lua Function Tools

Tactus supports defining tools as Lua functions directly within `.tac` files. These tools can perform custom operations and are automatically converted to Pydantic AI function toolsets.

### Individual Tool Declarations

Define single tools using assignment-based syntax:

```lua
-- Import done tool from standard library (recommended)
local done = require("tactus.tools.done")

-- Or define custom tools inline
calculate_tip = Tool {
    description = "Calculate tip amount for a bill",
    input = {
        bill_amount = field.number{
            required = true,
            description = "Total bill amount in dollars"
        },
        tip_percentage = field.number{
            required = true,
            description = "Tip percentage (e.g., 15 for 15%)"
        }
    },
    function(args)
        local tip = args.bill_amount * (args.tip_percentage / 100)
        local total = args.bill_amount + tip
        return string.format("Tip: $%.2f, Total: $%.2f", tip, total)
    end
}

-- Reference tools as variables in agent
assistant = Agent {
    provider = "openai",
    tools = {calculate_tip, done}  -- Variable references
}
```

Each `Tool {...}` assignment creates a callable tool handle.

### Direct Tool Invocation

`Tool {...}` returns a callable handle, enabling direct tool invocation from Lua code without agent involvement. This gives programmers deterministic control over when tools execute:

```lua
-- Tool returns a callable - assign it to use directly
calculate_tip = Tool {
    description = "Calculate tip amount for a bill",
    input = {
        bill_amount = field.number{required = true},
        tip_percentage = field.number{required = true}
    },
    function(args)
        local tip = args.bill_amount * (args.tip_percentage / 100)
        return string.format("Tip: $%.2f", tip)
    end
}

split_bill = Tool {
    description = "Split a bill among people",
    input = {
        total = field.number{required = true},
        people = field.integer{required = true}
    },
    function(args)
        return string.format("$%.2f per person", args.total / args.people)
    end
}

-- Call tools directly - deterministic, no LLM involvement
local tip_result = calculate_tip({bill_amount = 50, tip_percentage = 20})
local split_result = split_bill({total = 60, people = 3})

-- Pass multiple results to agent via context
assistant({
    context = {
        tip_calculation = tip_result,
        split_calculation = split_result
    }
})
```

Benefits of direct tool invocation:
- **Deterministic control**: Programmer decides exactly which tools run and when
- **Composable results**: Combine multiple tool outputs before passing to agents
- **Reduced token usage**: Tools run without LLM overhead
- **Testability**: Direct tool calls are easier to unit test

For external tools (MCP servers, plugins), use `Tool.get()`:

```lua
local web_search = Tool.get("web_search")  -- From MCP server
local result = web_search({query = "weather"})
```

### toolset() with type="lua"

Group multiple related tools into a named toolset:

```lua
toolset("math_tools", {
    type = "lua",
    tools = {
        {
            name = "add",
            description = "Add two numbers",
            parameters = {
                a = {type = "number", description = "First number", required = true},
                b = {type = "number", description = "Second number", required = true}
            },
            handler = function(args)
                return tostring(args.a + args.b)
            end
        },
        {
            name = "multiply",
            description = "Multiply two numbers",
            parameters = {
                a = {type = "number", required = true},
                b = {type = "number", required = true}
            },
            handler = function(args)
                return tostring(args.a * args.b)
            end
        }
    }
}

local done = require("tactus.tools.done")

calculator = Agent {
    provider = "openai",
    tools = {math_tools, done}  -- Variable references to toolsets and tools
}
```

This approach groups related tools and makes them available via a single variable reference.

### Inline Agent Tools

Define tools directly within agent configuration:

```lua
local done = require("tactus.tools.done")

text_processor = Agent {
    provider = "openai",
    system_prompt = "You process text",
    inline_tools = {
        {
            name = "uppercase",
            description = "Convert text to uppercase",
            input = {
                text = field.string{required = true, description = "Text to convert"}
            },
            handler = function(args)
                return string.upper(args.text)
            end
        },
        {
            name = "reverse",
            description = "Reverse text",
            input = {
                text = field.string{required = true}
            },
            handler = function(args)
                return string.reverse(args.text)
            end
        }
    },
    tools = {done}
}
```

Inline tools are automatically prefixed with the agent name (e.g., `text_processor_uppercase`).

**Tools in Agent Config**

In agent configuration:
- `tools` accepts **tool/toolset references** and toolset expressions.
- `inline_tools` is reserved for **inline tool definitions** (objects with `name`, `handler`, `input`).

```lua
local done = require("tactus.tools.done")
calculate_tip = Tool {...}
math_tools = Toolset {...}

example = Agent {
    inline_tools = {
        {name = "my_tool", handler = function(args) ... end, ...}  -- Inline
    },
    tools = {
        done,           -- Tool reference
        calculate_tip,  -- Tool reference
        math_tools,     -- Toolset reference
    }
}
```

In agent callable syntax, `tools` restricts which tools are available for this turn:
```lua
worker({tools = {search, done}})  -- Only these tools for this turn
worker({tools = {}})              -- No tools for this turn
```

### Parameter Types

Supported parameter types:

- `"string"` - Text values
- `"number"` - Floating-point numbers
- `"integer"` - Whole numbers
- `"boolean"` - true/false values
- `"table"` - Lua tables (converted to Python dicts)
- `"array"` - Lua arrays (converted to Python lists)

### Parameter Properties

- `type`: The parameter type (required)
- `description`: Helps the LLM understand the parameter (recommended)
- `required`: Whether the parameter must be provided (default: true)
- `default`: Default value if not provided (only for optional parameters)

### Tool Function Signatures

Tool handler functions receive a single argument - a table containing all parameters:

```lua
handler = function(args)
    -- args is a table: {param1 = value1, param2 = value2, ...}
    local result = args.param1 + args.param2
    return tostring(result)  -- Should return a string
end
```

### Integration with Tool Handles

Lua function tools provide handle methods for tracking calls and results:

```lua
-- Define tools
calculate_tip = Tool {
    description = "Calculate tip for a bill",
    input = { bill_amount = field.number{required = true} },
    function(args) return tostring(args.bill_amount * 0.2) end
}

Procedure {
    function(input)
        assistant({message = "Calculate something"})

        -- Check if tool was called (via tool variable)
        if calculate_tip.called() then
            Log.info("Tip calculator was used")

            -- Get the last result
            local result = calculate_tip.last_result()
            Log.info("Result: " .. result)
        end

        return {result = "done"}
    end
}
```

### Best Practices

1. **Clear Descriptions**: Provide detailed descriptions for both tools and parameters
2. **Type Safety**: Use appropriate types for parameters
3. **Error Handling**: Validate inputs and return error messages for invalid data
4. **Return Values**: Always return strings from handler functions
5. **Naming**: Use descriptive names that indicate the tool's purpose

### Examples

For comprehensive examples and patterns, see:
- `examples/18-feature-lua-tools-individual.tac`
- `examples/18-feature-lua-tools-toolset.tac`
- `examples/18-feature-lua-tools-inline.tac`
- [docs/TOOLS.md](docs/TOOLS.md) for detailed guide

---

## Invoking Procedures

Procedures can be invoked in multiple ways:

### As a Tool (Implicit)

```lua
coordinator = Agent {
    tools = {researcher},  -- Procedure as tool
    -- rest of agent config...
}
```

### Explicit Synchronous

```lua
local result = researcher.run({query = "quantum computing"})
```

### Explicit Asynchronous

```lua
local handle = researcher.spawn({query = "quantum computing"})
local status = handle.status()
local result = handle.wait()
```

## Exception Handling

```lua
local ok, result = pcall(Worker.turn)
if not ok then
  Log.error("Failed: " .. tostring(result))
  return {success = false, error = result}
end
```

---

## Primitive Reference

### Procedure Primitives

```lua
Procedure.run(name, params)              -- Sync invocation
Procedure.spawn(name, params)            -- Async invocation
Procedure.status(handle)                 -- Get status
Procedure.wait(handle)                   -- Wait for completion
Procedure.wait(handle, {timeout = n})    -- Wait with timeout
Procedure.inject(handle, message)        -- Send guidance
Procedure.cancel(handle)                 -- Abort
Procedure.wait_any(handles)              -- Wait for first
Procedure.wait_all(handles)              -- Wait for all
Procedure.is_complete(handle)            -- Check completion
Procedure.all_complete(handles)          -- Check all complete
```

### Step Primitives

For checkpointing arbitrary operations (not agent turns):

```lua
-- Execute fn and checkpoint result. On replay, return cached result.
-- Checkpoints are position-based (identified by execution order)
Step.checkpoint(fn)

-- Examples:
local champion = Step.checkpoint(function()
  return Tools.plexus_get_score({score_id = input.score_id})
end)

local metrics = Step.checkpoint(function()
  return Tools.plexus_run_evaluation({
    score_id = input.score_id,
    version = "champion"
  })
end)
```

Checkpoints are identified by their position in the execution order. Each call to `Step.checkpoint()` gets the next sequential position:

```lua
for i, item in ipairs(items) do
  -- Each iteration creates a new checkpoint at the next position
  local result = Step.checkpoint(function()
    return process(item)
  end)
end
```

### Checkpoint Control Primitives

For testing and debugging:

```lua
Checkpoint.clear_all()              -- Clear all checkpoints
Checkpoint.clear_after(position)    -- Clear checkpoint at position and all after (position is a number)
Checkpoint.next_position()          -- Get the next checkpoint position number
Checkpoint.exists(position)         -- Check if a checkpoint exists at a position
Checkpoint.get(position)            -- Get cached value at a position (or nil)
```

### Human Interaction Primitives

```lua
Human.approve({message, context, timeout, default, on_timeout})
-- Returns: boolean (approved or not)

Human.input({message, placeholder, timeout, default, on_timeout})
-- Returns: string (user input) or nil

Human.review({message, artifact, artifact_type, options, timeout})
-- Returns: {decision, feedback, edited_artifact, responded_at}

Human.notify({message, level, context})  -- level: info, warning, error
-- Returns: nil (non-blocking)

Human.escalate({message, context})
-- Blocks until human resolves

System.alert({message, level, source, context})  -- level: info, warning, error, critical
-- Returns: nil (non-blocking, can be called from anywhere)
```

### Agent Primitives (Callable Syntax)

```lua
worker()
worker({message = "...", tools = {...}})
worker({tools = {}})  -- No tools for this turn
worker({temperature = 0.3})  -- Override model settings
response.content
response.tool_calls
```

#### Per-Call Overrides

The callable agent accepts an optional table to override behavior for a single call:

**Available overrides:**
- `message` (string) - Message to send to the agent
- `context` (table) - Key-value pairs to pass as context to the agent (formatted as structured input)
- `tools` (list of toolset expressions) - Tools/toolsets available for this call (empty list = no tools)
- `temperature` (number) - Override temperature for this call
- `max_tokens` (number) - Override max_tokens for this call
- `top_p` (number) - Override top_p for this call

**Tool Override Behavior:**
- `tools` - List of tool/toolset references to enable: `{search, done, math_tools}`
- Empty list `{}`: No tools available for this call
- `nil`/omitted: Use agent's default configuration

**Examples:**

```lua
-- Normal call with all configured tools
worker()

-- Call with message (still has all tools)
worker({message = "Focus on security aspects"})

-- Call with context from tool results (for deterministic tool calling)
worker({
    context = {
        tip_calculation = tip_result,
        split_calculation = split_result,
        original_bill = "$50.00"
    }
})

-- Call with no tools (for summarization)
worker({
    message = "Summarize the search results above",
    tools = {}
})

-- Call with specific tools only (variable references)
worker({tools = {search, done}})

-- Call with a toolset
worker({tools = {math_tools}})  -- math_tools is a Toolset variable

-- Union of individual tools and toolsets
worker({
    tools = {search, math_tools}  -- Individual tools + toolset
})

-- Call with model parameter overrides
worker({
    message = "Be creative",
    temperature = 0.9,
    max_tokens = 1000
})
```

**Common pattern - Tool result summarization:**

```lua
repeat
    -- Main call: agent has all tools
    researcher()

    -- If tool was called (not done), summarize with no tools
    if search.called() or analyze.called() then
        researcher({
            message = "Summarize the tool results above in 2-3 sentences",
            tools = {}
        })
    end

until done.called()
```

### Session Primitives

```lua
Session.append({role, content})
Session.inject_system(text)
Session.clear()
Session.history()
Session.load_from_node(node)
Session.save_to_node(node)
```

### State Primitives

State is accessed via a metatable-enabled `state` variable:

```lua
-- Get a value
local value = state.key

-- Set a value
state.key = value

-- Check if exists
if state.key then ... end

-- Numeric operations
state.count = (state.count or 0) + 1

-- Helper functions for special operations
State.increment("count")         -- Increment numeric value (default by 1)
State.increment("count", 5)      -- Increment by specific amount
State.append("list", item)       -- Append to a list
State.all()                      -- Get all state as table
```

### Control Primitives

```lua
Stop.requested()
Stop.reason()

-- Tool handle methods (accessed via tool variable)
done.called()        -- Check if tool was called
done.last_result()   -- Get last result from tool

Iterations.current()
Iterations.exceeded(n)
```

### Graph Primitives

```lua
GraphNode.root()
GraphNode.current()
GraphNode.create({...})
GraphNode.set_current(node)
node:children()
node:parent()
node:score()
node:metadata()
node:set_metadata(key, value)
```

### Utility Primitives

```lua
Log.debug/info/warn/error(msg)
Retry.with_backoff(fn, opts)
Sleep(seconds)
Json.encode(table)
Json.decode(string)
File.read(path)
File.write(path, contents)
File.exists(path)
```

### Filesystem Helpers (stdlib)

Workflows sometimes need to enumerate files within the sandboxed working directory (for example, iterating over documents to lint or review). Use the filesystem helper module:

```lua
local fs = require("tactus.io.fs")

-- List entries in a directory (relative paths)
local entries = fs.list_dir("chapters", {files_only = true, sort = true})

-- Glob files (relative paths)
local qmd_files = fs.glob("chapters/*.qmd", {sort = true})
```

**Security model:** Paths are restricted to the procedure working directory; absolute paths and path traversal (`..`) are rejected.

**Determinism:** Filesystem contents can change between runs; wrap file enumeration and reads in `Step.checkpoint()` for durable workflows.

---

## Matchers

Matchers are utility functions for pattern matching and validation in workflows. They return tuple representations that can be used in assertions and conditional logic.

### Available Matchers

#### `contains(pattern)`

Checks if a string contains a specific substring.

```lua
local matcher = contains("error")
-- Returns: ("contains", "error")

-- Usage in assertions
if search.called() then
    local result = search.last_result()
    if matcher_matches(result, contains("success")) then
        Log.info("Search was successful")
    end
end
```

#### `equals(value)`

Checks for exact equality.

```lua
local matcher = equals("completed")
-- Returns: ("equals", "completed")

-- Usage
if state.status == "completed" then
    -- Exact match
end
```

#### `matches(regex)`

Checks if a string matches a regular expression pattern.

```lua
local matcher = matches("^[A-Z][a-z]+$")
-- Returns: ("matches", "^[A-Z][a-z]+$")

-- Usage for validation
local name = input.name
if string.match(name, "^[A-Z][a-z]+$") then
    Log.info("Valid name format")
end
```

### Integration with Validation

Matchers are primarily used in BDD specifications for testing:

```lua
Specification([[
Feature: Data Processing
  Scenario: Process valid data
    Given the procedure has started
    When the processor agent processes the data
    Then the result should contain "success"
    And the status should equal "completed"
    And the output should match "^[0-9]+$"
]])
```

### Matcher Tuples

Matchers return tuples that can be stored and passed around:

```lua
-- Store matchers for reuse
local success_matcher = contains("success")
local error_matcher = contains("error")

-- Use in conditional logic
local result = worker()
if tostring(result.output):find("success") then
    -- Contains success
elseif tostring(result.output):find("error") then
    -- Contains error
end
```

### Custom Matchers

You can create custom matcher-like functions:

```lua
local function between(min, max)
    return function(value)
        return value >= min and value <= max
    end
end

-- Usage
local check_range = between(1, 100)
if check_range(input.count) then
    Log.info("Count is in valid range")
end
```

---

## Example: HITL Workflow

```lua
-- Define tools
local done = require("tactus.tools.done")
research = Tool {
    description = "Research a topic",
    input = { query = field.string{required = true} },
    function(args) return "Research results for: " .. args.query end
}
write_draft = Tool {
    description = "Write a draft",
    input = { content = field.string{required = true} },
    function(args)
        state.draft = args.content
        return "Draft saved"
    end
}

-- Define agent
writer = Agent {
    provider = "openai",
    system_prompt = [[
You write content about: {input.topic}
Target: {input.target}
    ]],
    tools = {research, write_draft, done},
    filter = {class = "StandardFilter"}
}

-- Main procedure
Procedure {
    description = "Generate and publish content with human oversight",

    input = {
        topic = field.string{required = true},
        target = field.string{
            required = true,
            enum = {"blog", "docs", "internal"}
        }
    },

    output = {
        published = field.boolean{required = true},
        url = field.string{}
    },

    hitl = {
        review_content = {
            type = "review",
            message = "Review the generated content before publishing",
            timeout = 86400,
            options = {
                {label = "Approve", type = "action"},
                {label = "Reject", type = "cancel"},
                {label = "Revise", type = "action"}
            }
        },

        confirm_publish = {
            type = "approval",
            message = "Publish to {input.target}?",
            timeout = 3600,
            default = false
        }
    },

    function(input)
        Human.notify({
            message = "Starting content generation",
            level = "info",
            context = {topic = input.topic, target = input.target}
        })

        repeat
            writer()
        until done.called() or Iterations.exceeded(20)

        if not state.draft then
            return {published = false, error = "No draft generated"}
        end

        -- Human review
        local review = Human.review("review_content", {
            artifact = state.draft,
            artifact_type = "document"
        })

        if review.decision == "Reject" then
            Human.notify({
                message = "Content rejected",
                level = "warning",
                context = {feedback = review.feedback}
            })
            return {published = false, reason = "rejected"}
        elseif review.decision == "Revise" then
            -- Could loop back to writing with feedback
            state.revision_feedback = review.feedback
            -- ... revision logic ...
        end

        local final_content = review.edited_artifact or state.draft

        -- Approval to publish
        local approved = Human.approve("confirm_publish")

        if not approved then
            return {published = false, reason = "not_approved"}
        end

        local url = Step.checkpoint(function()
            return publish_content(final_content, input.target)
        end)

        Human.notify({
            message = "Content published successfully",
            level = "info",
            context = {url = url}
        })

        return {published = true, url = url}
    end
}
```

---

## Example: System Monitoring with Alerts

```lua
-- Main procedure
Procedure {
    input = {
        items = field.array{required = true},
        threshold = field.number{default = 0.1}
    },

    output = {
        processed = field.number{required = true},
        failed = field.number{required = true}
    },

    function(input)
        local processed = 0
        local failed = 0
        local total = #input.items

        for i, item in ipairs(input.items) do
            local ok, result = pcall(process_item, item)

            if ok then
                processed = processed + 1
            else
                failed = failed + 1
                Log.error("Item failed", {index = i, error = result})
            end

            -- Progress notification every 100 items
            if i % 100 == 0 then
                Human.notify({
                    message = "Processing progress: " .. i .. "/" .. total,
                    level = "info"
                })
            end

            -- Alert if failure rate exceeds threshold
            local failure_rate = failed / i
            if failure_rate > input.threshold then
                System.alert({
                    message = "Failure rate exceeded threshold",
                    level = "warning",
                    source = "batch_processor",
                    context = {
                        failure_rate = failure_rate,
                        threshold = input.threshold,
                        processed = i,
                        failed = failed
                    }
                })

                -- Ask human whether to continue
                local continue = Human.approve({
                    message = "Failure rate is " .. (failure_rate * 100) .. "%. Continue processing?",
                    default = false,
                    timeout = 300
                })

                if not continue then
                    break
                end
            end
        end

        -- Final status
        local level = failed > 0 and "warning" or "info"
        Human.notify({
            message = "Batch processing complete",
            level = level,
            context = {processed = processed, failed = failed, total = total}
        })

        return {processed = processed, failed = failed}
    end
}
```

---

---

---

## Example: Self-Optimizing Score System

A comprehensive example showing HITL with checkpointed tool calls, evaluation, and conditional retry.

**Note:** Tactus now exclusively uses the Lua DSL format (.tac files) for defining procedures. The previous YAML format is no longer supported. For a complete example of a self-optimizing system with HITL, checkpointed tool calls, and conditional retry, please refer to the example files in the `examples/` directory.

```lua
-- Self-optimizing Score system example demonstrating advanced patterns
-- Note: This is a complex example showing multiple advanced features

-- Define stages
-- Import completion tool from standard library
local done = require("tactus.tools.done")

-- Define agents (MCP tools referenced by string name in toolsets)
analyzer = Agent {
    provider = "openai",
    system_prompt = [[
You are a Score optimization specialist. Analyze the current
champion Score's performance and identify improvement opportunities.

Score ID: {input.score_id}
Champion metrics: {state.champion_metrics}
Error patterns: {state.error_analysis}
    ]],
    tools = {"plexus_get_score", "plexus_get_evaluation_metrics", "plexus_analyze_errors", "done"},
    max_turns = 20
}

drafter = Agent {
    provider = "openai",
    system_prompt = [[
Based on your analysis, draft an improved Score configuration.

Analysis findings: {state.analysis_findings}
Human feedback (if any): {state.human_feedback}

Be conservative - small targeted improvements are better than sweeping changes.
    ]],
    tools = {"plexus_draft_score_config", "plexus_validate_config", "done"},
    max_turns = 15
}

-- Main procedure
Procedure {
    description = "Self-optimizing system that drafts new Score configurations, evaluates them against the champion, and requests approval to promote improvements.",

    input = {
        score_id = field.string{required = true},
        improvement_threshold = field.number{default = 0.05},
        max_attempts = field.number{default = 3}
    },

    output = {
        promoted = field.boolean{required = true},
        new_version_id = field.string{},
        improvement = field.number{},
        rejection_reason = field.string{}
    },

    hitl = {
        approval_to_promote = {
            type = "review",
            message = "Review candidate Score performance and approve promotion",
            timeout = 86400,
            options = {
                {label = "Approve", type = "action"},
                {label = "Reject", type = "cancel"},
                {label = "Revise", type = "action"}
            }
        }
    },

    function(input)
        local attempt = 1

        -- Evaluate champion FIRST (checkpointed, runs once)

        state.champion_config = Step.checkpoint(function()
            return plexus_get_score.run({score_id = input.score_id})
        end)

        -- Run fresh evaluation on champion (checkpointed)
        state.champion_metrics = Step.checkpoint(function()
            return plexus_run_evaluation.run({
                score_id = input.score_id,
                version = "champion",
                test_set = "validation"
            })
        end)

        state.error_analysis = Step.checkpoint(function()
            return plexus_analyze_errors.run({
                score_id = input.score_id,
                limit = 100
            })
        end)

        while attempt <= input.max_attempts do
            Log.info("Optimization attempt " .. attempt)

            -- Agent analyzes the data
            repeat
                analyzer()
            until done.called() or Iterations.exceeded(20)

            state.analysis_findings = done.last_result()

            -- Draft improved configuration

            repeat
                drafter()
            until done.called() or Iterations.exceeded(15)

            local candidate_config = plexus_draft_score_config.last_result()
            if not candidate_config then
                return {promoted = false, rejection_reason = "drafting_failed"}
            end

            state.candidate_config = candidate_config

            -- Evaluate candidate (checkpointed per attempt)

            local eval_result = Step.checkpoint(function()
                return plexus_run_evaluation.run({
                    score_id = input.score_id,
                    config = candidate_config,
                    test_set = "validation"
                })
            end)

            state.candidate_metrics = eval_result.metrics

            local comparison = Step.checkpoint(function()
                return plexus_compare_metrics.run({
                    champion = state.champion_metrics,
                    candidate = eval_result.metrics
                })
            end)

            local improvement = comparison.improvement_percentage
            Log.info("Improvement: " .. (improvement * 100) .. "%")

            if improvement < input.improvement_threshold then
                if attempt < input.max_attempts then
                    state.human_feedback = "Auto-retry: " ..
                        (improvement * 100) .. "% below threshold"
                    attempt = attempt + 1
                else
                    return {
                        promoted = false,
                        improvement = improvement,
                        rejection_reason = "below_threshold"
                    }
                end
            else
                -- Request human approval

                local review = Human.review("approval_to_promote", {
                    artifact = {
                        candidate_config = candidate_config,
                        comparison = comparison,
                        champion_metrics = state.champion_metrics,
                        candidate_metrics = state.candidate_metrics
                    },
                    artifact_type = "score_promotion"
                })

                if review.decision == "Approve" then
                    local result = Step.checkpoint(function()
                        return plexus_promote_score_version.run({
                            score_id = input.score_id,
                            config = candidate_config
                        })
                    end)

                    Human.notify({
                        message = "Score promoted to new version",
                        level = "info",
                        context = {version_id = result.version_id}
                    })

                    return {
                        promoted = true,
                        new_version_id = result.version_id,
                        improvement = improvement
                    }

                elseif review.decision == "Revise" then
                    state.human_feedback = review.feedback
                    if review.edited_artifact then
                        state.candidate_config = review.edited_artifact
                    end
                    attempt = attempt + 1

                else  -- "Reject"
                    return {
                        promoted = false,
                        improvement = improvement,
                        rejection_reason = review.feedback or "rejected_by_human"
                    }
                end
            end
        end

        return {promoted = false, rejection_reason = "max_attempts_exhausted"}
    end
}
```

**Key patterns demonstrated:**

1. **Checkpointed tool calls** — `Step.checkpoint()` ensures expensive operations (evaluations) run once
2. **Champion evaluation at start** — Fresh baseline before any optimization attempts
3. **Position-based checkpoints** — Each checkpoint is identified by its execution order
4. **Three-way review decision** — Approve, Reject, or Revise with feedback loop
5. **State persistence across HITL** — All intermediate data survives the approval wait
6. **Automatic retry below threshold** — Doesn't bother human if improvement is too small

---

## Idempotent Execution Model

Procedures are designed for idempotent re-execution. Running a procedure multiple times produces the same result, with completed work skipped via checkpoints.

### The Core Algorithm

```
procedure_run(procedure_id):
    1. Load procedure and its chat session
    
    2. Find any PENDING_* messages (approval/input/review)
    
    3. For each PENDING_* message:
       - Look for a RESPONSE message with parentMessageId pointing to it
       - If no response exists: EXIT (still waiting, nothing to do)
       - If response exists: That's our resume value
    
    4. If we have pending messages with no responses:
       - This is a no-op, exit immediately
    
    5. If we have responses OR no pending messages:
       - Execute/resume the workflow
       - Replay completed checkpoints (return stored values)
       - Continue from where we left off
    
    6. Execute until:
       - Completion → mark complete, exit
       - HITL event → create PENDING_* message, checkpoint, exit
       - Error → handle per error_prompt, exit
```

### Checkpoint Storage

All checkpoints are stored in the `Procedure.metadata` field as JSON:

```json
{
  "checkpoints": [
    {
      "position": 0,
      "result": {"config": "...", "version": "v2.3"},
      "completed_at": "2024-12-04T10:00:00Z"
    },
    {
      "position": 1,
      "result": {"metrics": "...", "evaluation_id": "eval_123"},
      "completed_at": "2024-12-04T10:05:00Z"
    },
    {
      "position": 2,
      "result": {"improvement_percentage": 0.08},
      "completed_at": "2024-12-04T10:05:30Z"
    }
  ],
  "state": {
    "champion_config": "...",
    "champion_metrics": {"accuracy": 0.847},
    "candidate_config": "...",
    "attempt": 2
  },
  "lua_state": {
    "checkpoint_index": 3
  }
}
```

**Why procedure metadata:**
- Single record to load/save
- Atomic updates
- No additional tables or indexes needed
- Simple to inspect and debug

**Flushing checkpoints for testing:**

```bash
# Clear all checkpoints (restart from beginning)
plexus procedure reset <procedure_id>

# Clear checkpoints after a specific position
plexus procedure reset <procedure_id> --after 3

# Clear and rerun
plexus procedure reset <procedure_id> && plexus procedure run <procedure_id>
```

```lua
-- Programmatic checkpoint control (for testing)
Checkpoint.clear_all()
Checkpoint.clear_after(3)  -- Clear checkpoint at position 3 and beyond
```

### Replay Behavior

On re-execution:

```lua
-- First run: executes LLM call, stores result
local response = worker()  -- Checkpoint: call_1

-- Second run (replay): returns stored result immediately
local response = worker()  -- Returns checkpoint call_1's result

-- Continues to next uncompleted operation
local approved = Human.approve({message = "Continue?"})
-- If no response: exit
-- If response exists: return it and continue
```

### Determinism Requirements

Code between checkpoints must be deterministic:

```lua
-- GOOD: Deterministic
local items = input.items
for i, item in ipairs(items) do
  worker({message = "Process: " .. item})
end

-- BAD: Non-deterministic (different on replay)
local items = fetch_items_from_api()  -- Might return different results!
for i, item in ipairs(items) do
  worker({message = "Process: " .. item})
end

-- FIXED: Wrap non-deterministic operations in checkpointed steps
local items = Step.checkpoint(function()
  return fetch_items_from_api()
end)
for i, item in ipairs(items) do
  worker({message = "Process: " .. item})
end
```

### Resume Strategies

**Local Context:**

```bash
# Manual single procedure
plexus procedure resume <procedure_id>

# Resume all with pending responses
plexus procedure resume-all

# Polling daemon
plexus procedure watch --interval 10s
```

**Lambda Durable Context:**

Automatic. Lambda handles suspend/resume via callbacks. No polling needed.

---

## Migration from v3

| v3 | v4 | Notes |
|----|-----|-------|
| (none) | `hitl:` section | New: declarative HITL points |
| (none) | `Human.*` primitives | New: HITL interaction |
| (none) | `System.alert()` | New: programmatic alerts |
| (none) | `Step.checkpoint()` | New: checkpointed arbitrary operations (position-based) |
| (none) | `Checkpoint.*` | New: checkpoint control for testing |
| (none) | Execution Contexts | New: Local vs Lambda Durable abstraction |

All v3 procedures work unchanged in v4. HITL features are additive.

### v4.1 Clarifications

- **Checkpoint storage:** All in `Procedure.metadata`, not separate table
- **Review options:** Array of `{label, type}` hashes; label becomes decision value
- **Response fields:** `responded_at` timestamp included; no `responder_id` (no user records)
- **Step.checkpoint():** For checkpointing tool calls outside agent loops; position-based, not named

---

## Gherkin BDD Testing

Tactus includes first-class support for behavior-driven testing using Gherkin syntax.

### Specifications in Lua

Write Gherkin specifications directly in procedure files:

```lua
Specification([[
Feature: Research Task Completion
  As a user
  I want the agent to research topics effectively
  So that I get reliable results

  Scenario: Agent completes basic research
    Given the procedure has started
    When the researcher agent takes turns
    Then the search tool should be called at least once
    And the done tool should be called exactly once
    And the procedure should complete successfully
    And the total iterations should be less than 20
]])
```

### Built-in Steps

The framework provides comprehensive built-in steps for Tactus primitives:

**Tool steps:**
- `the {tool} tool should be called`
- `the {tool} tool should be called at least {n} times`
- `the {tool} tool should be called with {param}={value}`

**State steps:**
- `the state {key} should be {value}`
- `the state {key} should exist`

**Completion steps:**
- `the procedure has started`
- `the procedure should complete successfully`
- `the stop reason should contain {text}`

**Iteration steps:**
- `the total iterations should be less than {n}`
- `the agent should take at least {n} turns`

### Custom Steps

Define custom steps in Lua for advanced assertions:

```lua
step("the research quality is high", function()
  local results = state.research_results
  assert(#results > 5, "Should have at least 5 results")
  assert(results[1].quality == "high", "First result should be high quality")
end)
```

### Testing Commands

**Run tests (single run per scenario):**

```bash
tactus test procedure.tac
tactus test procedure.tac --scenario "Agent completes research"
```

**Evaluate consistency (multiple runs per scenario):**

```bash
tactus evaluate procedure.tac --runs 10
tactus evaluate procedure.tac --runs 50 --workers 10
```

### Evaluation Metrics

The `evaluate` command measures:
- **Success Rate** - Percentage of runs that passed
- **Consistency Score** - How often runs produce identical behavior (0.0 to 1.0)
- **Timing Statistics** - Mean, median, standard deviation
- **Flakiness Detection** - Identifies unreliable scenarios

### Parser Warnings

The validator warns if procedures have no specifications:

```
⚠ Warning: No specifications defined - consider adding BDD tests using specifications([[...]])
```

### Architecture

Tests are executed using Behave programmatically with:
- Parallel execution via multiprocessing
- Structured Pydantic results (no text parsing)
- IDE integration via structured log events
- Custom step definitions in Lua

---

## Summary

**Uniform Recursion:** Procedures work identically at all levels—same input, output, prompts, async, HITL.

**Human-in-the-Loop:** First-class primitives for approval, input, review, notification, and escalation.

**Message Classification:** Every message has a `humanInteraction` type controlling visibility and behavior.

**Declarative + Imperative:** Declare HITL points in YAML for documentation, invoke them in Lua for control.

**BDD Testing:** First-class Gherkin specifications with built-in steps, custom steps, parallel execution, and consistency evaluation.
