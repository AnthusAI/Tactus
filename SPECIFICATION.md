# Procedure DSL Specification v4

## Overview

The Procedure DSL enables defining agentic workflows as configuration. It combines declarative YAML for component definitions with embedded Lua for orchestration logic.

**Design Philosophy:**
- **YAML declares components** — agents, prompts, tools, filters, stages
- **Lua defines orchestration** — the actual workflow control flow
- **High-level primitives** — operations like `Worker.turn()` hide LLM mechanics
- **Uniform recursion** — a procedure invoked by another procedure works identically to a top-level procedure
- **Human-in-the-loop** — first-class support for human interaction, approval, and oversight
- **Built-in reliability** — retries, validation, and error handling under the hood

**Key Principles:**

1. **Uniform Recursion** — A procedure is a procedure, whether invoked externally or by another procedure. Same input, output, prompts, async capabilities everywhere.

2. **Human-in-the-Loop** — Procedures can request human approval, input, or review. Humans can monitor, intervene, and collaborate with running procedures.

---

## Lua DSL Format (.tac files)

**Recommended format** for defining procedures. Lua DSL provides better cohesion by grouping parameters and outputs with the procedure logic.

```lua
-- Agents are defined at top level (reusable across procedures)
agent("worker", {
    provider = "openai",
    model = "gpt-4o",
    system_prompt = "You are a helpful assistant",
    tools = {"done"}
})

-- Stages (optional)
stages({"planning", "executing", "complete"})

-- Procedure with input and output defined inline
procedure({
    -- Input (inputs to the procedure)
    input = {
        task = {
            type = "string",
            required = true,
            description = "The task to perform"
        },
        max_iterations = {
            type = "number",
            default = 10
        }
    },

    -- Output (validated return values)
    output = {
        result = {
            type = "string",
            required = true,
            description = "The result of the task"
        },
        success = {
            type = "boolean",
            required = true
        }
    },

    -- State (persistent working data)
    state = {}
}, function()
    -- Procedure logic here
    local task = input.task
    Log.info("Starting task", {task = task})

    repeat
        Worker.turn()
    until Tool.called("done") or Iterations.exceeded(input.max_iterations)
    
    return {
        result = "Task completed",
        success = true
    }
end)

-- BDD Specifications (optional)
specifications([[
Feature: Task Processing
  Scenario: Task completes successfully
    Given the procedure has started
    When the procedure runs
    Then the done tool should be called
    And the procedure should complete successfully
]])
```

**Key structure:**
- **Agents** at top level (reusable)
- **procedure()** takes two arguments:
  1. Config table with `input`, `output`, and `state`
  2. Function containing the procedure logic
- **Input** and **output** are defined inside the procedure config, not at top level
- **specifications()** at top level for BDD tests

---

## Input

Input schema defines what the procedure accepts. Validated before execution.

```lua
procedure({
    input = {
        topic = {
            type = "string",
            required = true,
            description = "The topic to research"
        },
        depth = {
            type = "string",
            enum = {"shallow", "deep"},
            default = "shallow"
        },
        max_results = {
            type = "number",
            default = 10
        },
        include_sources = {
            type = "boolean",
            default = true
        }
    },

    state = {}
}, function()
    -- Access input
    local topic = input.topic
    local depth = input.depth
    -- ...
end)
```

**Type options:** `string`, `number`, `boolean`, `array`, `object`

Input values are accessed in templates as `{input.topic}` and in Lua as `input.topic`.

---

## Output

Output schema defines what the procedure returns. Validated after execution.

```lua
procedure({
    output = {
        findings = {
            type = "string",
            required = true,
            description = "Research findings summary"
        },
        confidence = {
            type = "string",
            enum = {"high", "medium", "low"},
            required = true
        },
        sources = {
            type = "array",
            required = false
        }
    },

    state = {}
}, function()
    -- Procedure logic
    return {
        findings = "...",
        confidence = "high",
        sources = {...}
    }
end)
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
procedure({
    message_history = {
        mode = "isolated",  -- or "shared"
        max_tokens = 120000,
        filter = filters.last_n(50)
    }
}, function()
    -- Access message history via MessageHistory primitive
    MessageHistory.inject_system("Context for next turn")
    local history = MessageHistory.get()
end)
```

**Message history modes:**
- `isolated` (default): Each agent has its own conversation history
- `shared`: All agents share a common conversation history

**Message history filters:**
- `filters.last_n(n)` - Keep only last N messages
- `filters.token_budget(max)` - Keep messages within token budget
- `filters.by_role(role)` - Filter by message role
- `filters.compose(...)` - Combine multiple filters

**Agent-level overrides:**

Agents can override procedure-level message history settings:

```lua
agent("researcher", {
    provider = "openai",
    model = "gpt-4o",
    system_prompt = "Research the topic",
    tools = {"search", "done"},
    
    message_history = {
        source = "shared",  -- Use shared history
        filter = filters.compose(
            filters.token_budget(80000),
            filters.last_n(20)
        )
    }
})
```

---

## Structured Output (output_type)

Agents can enforce structured output schemas using `output_type`, aligned with pydantic-ai's validation and automatic retry.

**Lua DSL format (.tac):**

```lua
agent("extractor", {
    provider = "openai",
    model = "gpt-4o",
    system_prompt = "Extract structured data from user input",
    tools = {"done"},
    
    -- Define structured output schema (aligned with pydantic-ai's output_type)
    output_type = {
        name = {type = "string", required = true},
        age = {type = "number", required = true},
        email = {type = "string", required = false}
    }
})
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

`Agent.turn()` returns a `Result` object (not raw data) with access to response data, token usage, and conversation history.

**Aligned with pydantic-ai:** The Result object wraps pydantic-ai's `RunResult` and provides Lua-accessible properties.

**Properties:**
- `result.data` - The response (text string or structured data dict)
- `result.usage` - Token usage stats (prompt_tokens, completion_tokens, total_tokens)

**Methods:**
- `result.new_messages()` - Messages from this turn only
- `result.all_messages()` - Full conversation history
- `result.cost()` - Token usage (same as .usage, for cost calculation)

**Example:**

```lua
procedure({}, function()
    local result = Agent.turn()
    
    -- Access response data
    Log.info("Response", {data = result.data})
    
    -- Access token usage
    Log.info("Tokens used", {
        prompt = result.usage.prompt_tokens,
        completion = result.usage.completion_tokens,
        total = result.usage.total_tokens
    })
    
    -- Access messages
    local messages = result.new_messages()
    for i, msg in ipairs(messages) do
        Log.info("Message", {role = msg.role, content = msg.content})
    end
end)
```

**With structured output:**

```lua
agent("extractor", {
    output_type = {
        city = {type = "string", required = true},
        country = {type = "string", required = true}
    }
})

procedure({}, function()
    local result = Extractor.turn()
    
    -- Access structured data fields
    Log.info("Extracted", {
        city = result.data.city,
        country = result.data.country
    })
end)
```

---

## Summarization Prompts

These prompts control how the procedure communicates its results:

### `return_prompt:`

Injected when the procedure completes successfully. The agent does one final turn to generate a summary, which becomes the return value.

```yaml
return_prompt: |
  Summarize your work:
  - What was accomplished
  - Key findings or results
  - Any important notes for the caller
```

### `error_prompt:`

Injected when the procedure fails (exception or max iterations exceeded). The agent explains what went wrong.

```yaml
error_prompt: |
  The task could not be completed. Explain:
  - What you were attempting
  - What went wrong
  - Any partial progress made
```

### `status_prompt:`

Injected when a caller requests a status update (async procedures only). The agent reports current progress without stopping.

```yaml
status_prompt: |
  Provide a brief progress update:
  - What has been completed
  - What you're currently working on
  - Estimated remaining work
```

### Defaults

If not specified:

```yaml
return_prompt: |
  Summarize the result of your work concisely.

error_prompt: |
  Explain what went wrong and any partial progress made.

status_prompt: |
  Briefly describe your current progress and remaining work.
```

---

## Async and Recursion Settings

```yaml
# Enable async invocation (caller can spawn and continue)
async: true

# Maximum recursion depth (prevents infinite recursion)
max_depth: 5

# Maximum turns for this procedure
max_turns: 50

# Checkpoint interval for recovery (async only)
checkpoint_interval: 10
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
│  Worker.turn() / Human.approve() / etc.     │
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
| `Worker.turn()` | DB checkpoint before/after | `context.step()` |
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

```yaml
guards:
  - |
    if not File.exists(input.file_path) then
      return false, "File not found: " .. input.file_path
    end
    return true

  - |
    if input.depth > 10 then
      return false, "Depth cannot exceed 10"
    end
    return true
```

Guards return `true` to proceed or `false, "error message"` to abort.

---

## Dependencies

Tactus supports declaring external resource dependencies (HTTP clients, databases, caches) that are automatically initialized and injected into your procedure.

### Resource Dependencies

Declare resources your procedure needs (HTTP APIs, databases, caches, etc.):

```lua
procedure({
    input = {
        city = {type = "string", required = true}
    },

    -- Declare resource dependencies
    dependencies = {
        weather_api = {
            type = "http_client",
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

    state = {}
}, function()
    -- Dependencies are automatically created and available
    -- Tools (via MCP) can access them through the dependency injection system
    Worker.turn()
    return {result = "done"}
end)
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

Optionally validate that required tools and procedures exist:

```yaml
dependencies:
  tools:
    - web_search
    - read_document
  procedures:
    - researcher
    - analyzer
```

If any dependency is missing, the procedure fails fast with a clear error.

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
procedure({
    dependencies = {
        api_client = {type = "http_client", base_url = "https://api.example.com"}
    }
}, function()
    -- Child procedure uses same api_client instance
    local child_result = ChildProcedure.run({...})
end)
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
  State.set("human_feedback", review.feedback)
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
    attempts = State.get("resolution_attempts"),
    last_error = last_error,
    current_state = State.all()
  }
})
-- Procedure pauses until human resolves and resumes
```

### Declarative HITL Points

For predictable workflows, declare interaction points in YAML:

```yaml
hitl:
  review_draft:
    type: review
    message: "Please review the generated document"
    timeout: 86400
    options: [approve, edit, reject]
    
  confirm_publish:
    type: approval
    message: "Publish this document to production?"
    timeout: 3600
    default: false
    
  get_topic:
    type: input
    message: "What topic should be researched?"
    placeholder: "Enter topic..."
```

Reference in procedure:

```lua
-- Uses the declared configuration
local review = Human.review("review_draft", {artifact = draft})
local approved = Human.approve("confirm_publish")
local topic = Human.input("get_topic")
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

### HITL Stage Integration

When a procedure is waiting for human interaction, its stage reflects this:

```lua
Stage.set("processing")
do_work()

-- Procedure status becomes "waiting_for_human" during this call
local approved = Human.approve({message = "Continue?"})

Stage.set("finalizing")
```

Parent procedures can detect this:

```lua
local handle = Procedure.spawn("deployment", params)

local status = Procedure.status(handle)
if status.waiting_for_human then
  -- Maybe notify via Slack
  notify_channel("Deployment waiting for approval")
end
```

---

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

## Inline Procedure Definitions

For convenience, procedures can be defined inline:

```yaml
name: coordinator
version: 1.0.0

procedures:
  researcher:
    description: "Researches a topic"

    input:
      query:
        type: string
        required: true

    output:
      findings:
        type: string
        required: true

    state: {}

    return_prompt: |
      Summarize your research findings.

    agents:
      worker:
        system_prompt: |
          Research: {input.query}
        tools: [search, done]

    procedure: |
      repeat
        Worker.turn()
      until Tool.called("done")

agents:
  coordinator:
    tools:
      - researcher
      - done

procedure: |
  Coordinator.turn()
```

Inline procedures follow the **exact same structure** as top-level procedures.

---

## Agent Definitions

Agents are the cognitive workers within a procedure:

```yaml
agents:
  worker:
    prepare: |
      return {
        current_time = os.date(),
        data = load_context_data()
      }

    system_prompt: |
      You are processing: {input.task}
      Context: {prepared.data}

    initial_message: |
      Begin working on the task.
    
    tools:
      - search
      - analyze
      - researcher  # Another procedure
      - done
    
    filter:
      class: ComposedFilter
      chain:
        - class: TokenBudget
          max_tokens: 120000
        - class: LimitToolResults
          count: 2
    
    response:
      retries: 3
      retry_delay: 1.0
    
    max_turns: 50
```

When you declare an agent named `worker`, the primitive `Worker.turn()` becomes available in Lua.

### Model Configuration

Agents can specify which LLM model to use and configure model-specific parameters. The `model` field accepts either a simple string or a dictionary with settings.

**Simple string format** (for default settings):

```yaml
agents:
  greeter:
    model: gpt-4o-mini
    system_prompt: "You are a friendly greeter."
    tools: [done]
```

**Dictionary format** (with custom settings):

```yaml
agents:
  creative_writer:
    model:
      name: gpt-4o
      temperature: 0.9
      top_p: 0.95
      max_tokens: 2000
    system_prompt: "You are a creative writer."
    tools: [done]
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

```yaml
agents:
  analyst:
    model:
      name: gpt-5
      openai_reasoning_effort: high
      max_tokens: 4000
    system_prompt: "Analyze the data carefully."
    tools: [done]
  
  summarizer:
    model:
      name: gpt-4o-mini
      temperature: 0.3
      max_tokens: 500
    system_prompt: "Summarize concisely."
    tools: [done]
```

**Provider specification:**

**IMPORTANT:** Every agent must specify a `provider:` (either directly on the agent or via `default_provider:` at the procedure level). Supported providers are `openai` and `bedrock`.

```yaml
agents:
  openai_agent:
    provider: openai
    model: gpt-4o
    system_prompt: "You are a helpful assistant."
    tools: [done]
  
  bedrock_agent:
    provider: bedrock
    model: anthropic.claude-3-5-sonnet-20240620-v1:0
    system_prompt: "You are a helpful assistant."
    tools: [done]
```

**Using procedure-level defaults:**

You can set `default_provider:` and `default_model:` at the procedure level to avoid repeating them:

```yaml
default_model: gpt-4o-mini
default_provider: openai

agents:
  worker:
    # Uses default_model and default_provider
    system_prompt: "Process the task."
    tools: [done]
  
  specialist:
    model: gpt-4o  # Override just the model, still uses default_provider
    system_prompt: "Handle complex reasoning."
    tools: [done]
```

**Mixed providers in one procedure:**

```yaml
agents:
  openai_agent:
    provider: openai
    model: gpt-4o-mini
    system_prompt: "Fast processing with OpenAI."
    tools: [done]
  
  bedrock_agent:
    provider: bedrock
    model: anthropic.claude-3-5-sonnet-20240620-v1:0
    system_prompt: "Deep analysis with Claude."
    tools: [done]
```

---

## Lua Function Tools

Tactus supports defining tools as Lua functions directly within `.tac` files. These tools can perform custom operations and are automatically converted to Pydantic AI function toolsets.

### Individual tool() Declarations

Define single tools that can be referenced by name:

```lua
tool("calculate_tip", {
    description = "Calculate tip amount for a bill",
    parameters = {
        bill_amount = {
            type = "number",
            description = "Total bill amount in dollars",
            required = true
        },
        tip_percentage = {
            type = "number",
            description = "Tip percentage (e.g., 15 for 15%)",
            required = true
        }
    }
}, function(args)
    local tip = args.bill_amount * (args.tip_percentage / 100)
    local total = args.bill_amount + tip
    return string.format("Tip: $%.2f, Total: $%.2f", tip, total)
end)

-- Reference the tool by name in agent toolsets
agent("assistant", {
    provider = "openai",
    toolsets = {"calculate_tip", "done"}
})
```

Each `tool()` declaration creates a single-tool toolset accessible by the tool's name.

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
})

agent("calculator", {
    provider = "openai",
    toolsets = {"math_tools", "done"}
})
```

This approach groups related tools and makes them available as a single toolset reference.

### Inline Agent Tools

Define tools directly within agent configuration:

```lua
agent("text_processor", {
    provider = "openai",
    system_prompt = "You process text",
    tools = {
        {
            name = "uppercase",
            description = "Convert text to uppercase",
            parameters = {
                text = {type = "string", description = "Text to convert", required = true}
            },
            handler = function(args)
                return string.upper(args.text)
            end
        },
        {
            name = "reverse",
            description = "Reverse text",
            parameters = {
                text = {type = "string", required = true}
            },
            handler = function(args)
                return string.reverse(args.text)
            end
        }
    },
    toolsets = {"done"}  -- Can mix inline tools with toolsets
})
```

Inline tools are automatically prefixed with the agent name (e.g., `text_processor_uppercase`).

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

### Integration with Tool Primitive

Lua function tools fully integrate with the `Tool` primitive for tracking:

```lua
procedure(function()
    Assistant.turn("Calculate something")

    -- Check if tool was called
    if Tool.called("calculate_tip") then
        Log.info("Tip calculator was used")

        -- Get the last call details
        local call = Tool.last_call("calculate_tip")
        Log.info("Args: " .. tostring(call.args.bill_amount))
        Log.info("Result: " .. call.result)
    end

    return {result = "done"}
end)
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

```yaml
agents:
  coordinator:
    tools:
      - researcher  # Procedure name
```

### Explicit Synchronous

```lua
local result = Procedure.run("researcher", {query = "quantum computing"})
```

### Explicit Asynchronous

```lua
local handle = Procedure.spawn("researcher", {query = "quantum computing"})
local status = Procedure.status(handle)
local result = Procedure.wait(handle)
```

---

## Stages

Stages integrate with TaskStages monitoring:

```yaml
stages:
  - planning
  - executing
  - awaiting_human  # HITL wait
  - complete
```

```lua
Stage.set("planning")
Stage.advance("executing")
Stage.is("planning")  -- false
Stage.current()       -- "executing"
```

---

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
Step.run(name, fn)

-- Examples:
local champion = Step.run("load_champion", function()
  return Tools.plexus_get_score({score_id = input.score_id})
end)

local metrics = Step.run("evaluate_champion", function()
  return Tools.plexus_run_evaluation({
    score_id = input.score_id,
    version = "champion"
  })
end)

-- Named steps allow targeted cache clearing for testing
```

Step names must be unique within a procedure execution. Use descriptive names or append counters for loops:

```lua
for i, item in ipairs(items) do
  local result = Step.run("process_item_" .. i, function()
    return process(item)
  end)
end
```

### Checkpoint Control Primitives

For testing and debugging:

```lua
Checkpoint.clear_all()              -- Clear all checkpoints
Checkpoint.clear_after(name)        -- Clear this checkpoint and all after
Checkpoint.exists(name)             -- Check if checkpoint exists
Checkpoint.get(name)                -- Get cached value (or nil)
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

### Agent Primitives

```lua
Worker.turn()
Worker.turn({inject = "...", tools = {...}})
Worker.turn({tools = {}})  -- No tools for this turn
Worker.turn({temperature = 0.3})  -- Override model settings
response.content
response.tool_calls
```

#### Per-Turn Overrides

The `turn()` method accepts an optional table to override behavior for a single turn:

**Available overrides:**
- `inject` (string) - Message to inject for this turn (overrides normal conversation flow)
- `tools` (list of strings) - Tool names available for this turn (empty list = no tools)
- `temperature` (number) - Override temperature for this turn
- `max_tokens` (number) - Override max_tokens for this turn
- `top_p` (number) - Override top_p for this turn

**Examples:**

```lua
-- Normal turn with all configured tools
Worker.turn()

-- Turn with injected message (still has all tools)
Worker.turn({inject = "Focus on security aspects"})

-- Turn with no tools (for summarization)
Worker.turn({
    inject = "Summarize the search results above",
    tools = {}
})

-- Turn with specific tools only
Worker.turn({tools = {"search", "done"}})

-- Turn with model parameter overrides
Worker.turn({
    inject = "Be creative",
    temperature = 0.9,
    max_tokens = 1000
})
```

**Common pattern - Tool result summarization:**

```lua
repeat
    -- Main turn: agent has all tools
    Researcher.turn()
    
    -- If tool was called (not done), summarize with no tools
    if Tool.called("search") or Tool.called("analyze") then
        Researcher.turn({
            inject = "Summarize the tool results above in 2-3 sentences",
            tools = {}
        })
    end
    
until Tool.called("done")
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

```lua
State.get(key)
State.get(key, default)
State.set(key, value)
State.increment(key)
State.append(key, value)
State.all()
```

### Stage Primitives

```lua
Stage.current()
Stage.set(name)
Stage.advance(name)
Stage.is(name)
Stage.history()
```

### Control Primitives

```lua
Stop.requested()
Stop.reason()
Tool.called(name)
Tool.last_result(name)
Tool.last_call(name)
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
if Tool.called("search") then
    local result = Tool.last_result("search")
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
local status = State.get("status")
if status == "completed" then
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
specifications([[
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
local result = Worker.turn()
if result.data:find("success") then
    -- Contains success
elseif result.data:find("error") then
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

```yaml
name: content_pipeline
version: 1.0.0
description: Generate and publish content with human oversight

input:
  topic:
    type: string
    required: true
  target:
    type: string
    enum: [blog, docs, internal]
    required: true

output:
  published:
    type: boolean
    required: true
  url:
    type: string
    required: false

state: {}

hitl:
  review_content:
    type: review
    message: "Review the generated content before publishing"
    timeout: 86400
    options:
      - {label: "Approve", type: "action"}
      - {label: "Reject", type: "cancel"}
      - {label: "Revise", type: "action"}

  confirm_publish:
    type: approval
    message: "Publish to {input.target}?"
    timeout: 3600
    default: false

agents:
  writer:
    system_prompt: |
      You write content about: {input.topic}
      Target: {input.target}
    tools:
      - research
      - write_draft
      - done
    filter:
      class: StandardFilter

stages:
  - researching
  - writing
  - review
  - publishing
  - complete

procedure: |
  Stage.set("researching")
  Human.notify({
    message = "Starting content generation",
    level = "info",
    context = {topic = input.topic, target = input.target}
  })
  
  Stage.set("writing")
  repeat
    Writer.turn()
  until Tool.called("done") or Iterations.exceeded(20)
  
  local draft = State.get("draft")
  if not draft then
    return {published = false, error = "No draft generated"}
  end
  
  -- Human review
  Stage.set("review")
  local review = Human.review("review_content", {
    artifact = draft,
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
    State.set("revision_feedback", review.feedback)
    -- ... revision logic ...
  end

  local final_content = review.edited_artifact or draft

  -- Approval to publish
  Stage.set("publishing")
  local approved = Human.approve("confirm_publish")

  if not approved then
    return {published = false, reason = "not_approved"}
  end

  local url = Step.run("publish", function()
    return publish_content(final_content, input.target)
  end)
  
  Human.notify({
    message = "Content published successfully",
    level = "info",
    context = {url = url}
  })
  
  Stage.set("complete")
  return {published = true, url = url}
```

---

## Example: System Monitoring with Alerts

```yaml
name: batch_processor
version: 1.0.0

input:
  items:
    type: array
    required: true
  threshold:
    type: number
    default: 0.1

output:
  processed:
    type: number
    required: true
  failed:
    type: number
    required: true

state: {}

stages:
  - processing
  - complete

procedure: |
  local processed = 0
  local failed = 0
  local total = #input.items

  Stage.set("processing")

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
  
  Stage.set("complete")
  
  -- Final status
  local level = failed > 0 and "warning" or "info"
  Human.notify({
    message = "Batch processing complete",
    level = level,
    context = {processed = processed, failed = failed, total = total}
  })
  
  return {processed = processed, failed = failed}
```

---

---

---

## Example: Self-Optimizing Score System

A comprehensive example showing HITL with checkpointed tool calls, evaluation, and conditional retry:

```yaml
name: score_optimizer
version: 1.0.0
description: |
  Self-optimizing system that drafts new Score configurations,
  evaluates them against the champion, and requests approval
  to promote improvements.

input:
  score_id:
    type: string
    required: true
  improvement_threshold:
    type: number
    default: 0.05
  max_attempts:
    type: number
    default: 3

output:
  promoted:
    type: boolean
    required: true
  new_version_id:
    type: string
    required: false
  improvement:
    type: number
    required: false
  rejection_reason:
    type: string
    required: false

state: {}

hitl:
  approval_to_promote:
    type: review
    message: "Review candidate Score performance and approve promotion"
    timeout: 86400
    options:
      - {label: "Approve", type: "action"}
      - {label: "Reject", type: "cancel"}
      - {label: "Revise", type: "action"}

stages:
  - analyzing
  - drafting
  - evaluating
  - awaiting_approval
  - promoting
  - complete

prompts:
  analysis_system: |
    You are a Score optimization specialist. Analyze the current
    champion Score's performance and identify improvement opportunities.

    Score ID: {input.score_id}
    Champion metrics: {state.champion_metrics}
    Error patterns: {state.error_analysis}

  drafting_system: |
    Based on your analysis, draft an improved Score configuration.

    Analysis findings: {state.analysis_findings}
    Human feedback (if any): {state.human_feedback}

    Be conservative - small targeted improvements are better than
    sweeping changes.

agents:
  analyzer:
    system_prompt: prompts.analysis_system
    tools:
      - plexus_get_score
      - plexus_get_evaluation_metrics
      - plexus_analyze_errors
      - done
    max_turns: 20

  drafter:
    system_prompt: prompts.drafting_system
    tools:
      - plexus_draft_score_config
      - plexus_validate_config
      - done
    max_turns: 15

procedure: |
  local attempt = 1
  
  -----------------------------------------------------------------
  -- Evaluate champion FIRST (checkpointed, runs once)
  -----------------------------------------------------------------
  Stage.set("analyzing")
  
  State.set("champion_config", Step.run("load_champion", function()
    return Tools.plexus_get_score({score_id = input.score_id})
  end))

  -- Run fresh evaluation on champion (checkpointed)
  State.set("champion_metrics", Step.run("evaluate_champion", function()
    return Tools.plexus_run_evaluation({
      score_id = input.score_id,
      version = "champion",
      test_set = "validation"
    })
  end))

  State.set("error_analysis", Step.run("analyze_errors", function()
    return Tools.plexus_analyze_errors({
      score_id = input.score_id,
      limit = 100
    })
  end))

  while attempt <= input.max_attempts do
    Log.info("Optimization attempt " .. attempt)
    
    -- Agent analyzes the data
    repeat
      Analyzer.turn()
    until Tool.called("done") or Iterations.exceeded(20)
    
    State.set("analysis_findings", Tool.last_result("done"))
    
    -----------------------------------------------------------------
    -- Draft improved configuration
    -----------------------------------------------------------------
    Stage.set("drafting")
    
    repeat
      Drafter.turn()
    until Tool.called("done") or Iterations.exceeded(15)
    
    local candidate_config = Tool.last_result("plexus_draft_score_config")
    if not candidate_config then
      return {promoted = false, rejection_reason = "drafting_failed"}
    end
    
    State.set("candidate_config", candidate_config)
    
    -----------------------------------------------------------------
    -- Evaluate candidate (checkpointed per attempt)
    -----------------------------------------------------------------
    Stage.set("evaluating")
    
    local eval_result = Step.run("evaluate_candidate_" .. attempt, function()
      return Tools.plexus_run_evaluation({
        score_id = input.score_id,
        config = candidate_config,
        test_set = "validation"
      })
    end)
    
    State.set("candidate_metrics", eval_result.metrics)
    
    local comparison = Step.run("compare_" .. attempt, function()
      return Tools.plexus_compare_metrics({
        champion = State.get("champion_metrics"),
        candidate = eval_result.metrics
      })
    end)
    
    local improvement = comparison.improvement_percentage
    Log.info("Improvement: " .. (improvement * 100) .. "%")

    if improvement < input.improvement_threshold then
      if attempt < input.max_attempts then
        State.set("human_feedback", "Auto-retry: " ..
          (improvement * 100) .. "% below threshold")
        attempt = attempt + 1
      else
        return {
          promoted = false,
          improvement = improvement,
          rejection_reason = "below_threshold"
        }
      end
    else
      -----------------------------------------------------------------
      -- Request human approval
      -----------------------------------------------------------------
      Stage.set("awaiting_approval")
      
      local review = Human.review("approval_to_promote", {
        artifact = {
          candidate_config = candidate_config,
          comparison = comparison,
          champion_metrics = State.get("champion_metrics"),
          candidate_metrics = State.get("candidate_metrics")
        },
        artifact_type = "score_promotion"
      })
      
      if review.decision == "Approve" then
        Stage.set("promoting")

        local result = Step.run("promote", function()
          return Tools.plexus_promote_score_version({
            score_id = input.score_id,
            config = candidate_config
          })
        end)
        
        Human.notify({
          message = "Score promoted to new version",
          level = "info",
          context = {version_id = result.version_id}
        })
        
        Stage.set("complete")
        return {
          promoted = true,
          new_version_id = result.version_id,
          improvement = improvement
        }
        
      elseif review.decision == "Revise" then
        State.set("human_feedback", review.feedback)
        if review.edited_artifact then
          State.set("candidate_config", review.edited_artifact)
        end
        attempt = attempt + 1
        
      else  -- "Reject"
        Stage.set("complete")
        return {
          promoted = false,
          improvement = improvement,
          rejection_reason = review.feedback or "rejected_by_human"
        }
      end
    end
  end
  
  Stage.set("complete")
  return {promoted = false, rejection_reason = "max_attempts_exhausted"}
```

**Key patterns demonstrated:**

1. **Checkpointed tool calls** — `Step.run()` ensures expensive operations (evaluations) run once
2. **Champion evaluation at start** — Fresh baseline before any optimization attempts
3. **Named checkpoints per attempt** — `"evaluate_candidate_" .. attempt` allows reruns of specific attempts
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

```yaml
# Procedure.metadata structure
checkpoints:
  load_champion:
    result: {config: {...}, version: "v2.3"}
    completed_at: "2024-12-04T10:00:00Z"
    
  run_evaluation_1:
    result: {metrics: {...}, evaluation_id: "eval_123"}
    completed_at: "2024-12-04T10:05:00Z"
    
  compare_metrics_1:
    result: {improvement_percentage: 0.08, ...}
    completed_at: "2024-12-04T10:05:30Z"

state:
  champion_config: {...}
  champion_metrics: {accuracy: 0.847, ...}
  candidate_config: {...}
  attempt: 2

lua_state:
  # Serialized coroutine position for resume
  checkpoint_index: 5
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

# Clear checkpoints after a specific point
plexus procedure reset <procedure_id> --after "run_evaluation_1"

# Clear and rerun
plexus procedure reset <procedure_id> && plexus procedure run <procedure_id>
```

```lua
-- Programmatic checkpoint control (for testing)
Checkpoint.clear_all()
Checkpoint.clear_after("step_name")
Checkpoint.exists("step_name")  -- returns boolean
```

### Replay Behavior

On re-execution:

```lua
-- First run: executes LLM call, stores result
local response = Worker.turn()  -- Checkpoint: turn_1

-- Second run (replay): returns stored result immediately
local response = Worker.turn()  -- Returns checkpoint turn_1's result

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
  Worker.turn({inject = "Process: " .. item})
end

-- BAD: Non-deterministic (different on replay)
local items = fetch_items_from_api()  -- Might return different results!
for i, item in ipairs(items) do
  Worker.turn({inject = "Process: " .. item})
end

-- FIXED: Wrap non-deterministic operations in checkpointed steps
local items = Step.run("fetch_items", function()
  return fetch_items_from_api()
end)
for i, item in ipairs(items) do
  Worker.turn({inject = "Process: " .. item})
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
| (none) | `Step.run()` | New: checkpointed arbitrary operations |
| (none) | `Checkpoint.*` | New: checkpoint control for testing |
| (none) | Execution Contexts | New: Local vs Lambda Durable abstraction |

All v3 procedures work unchanged in v4. HITL features are additive.

### v4.1 Clarifications

- **Checkpoint storage:** All in `Procedure.metadata`, not separate table
- **Review options:** Array of `{label, type}` hashes; label becomes decision value
- **Response fields:** `responded_at` timestamp included; no `responder_id` (no user records)
- **Step.run():** For checkpointing tool calls outside agent loops

---

## Gherkin BDD Testing

Tactus includes first-class support for behavior-driven testing using Gherkin syntax.

### Specifications in Lua

Write Gherkin specifications directly in procedure files:

```lua
specifications([[
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

  Scenario: Agent progresses through stages correctly
    Given the procedure has started
    When the procedure runs
    Then the stage should transition from researching to complete
    And the total iterations should be less than 20
]])
```

### Built-in Steps

The framework provides comprehensive built-in steps for Tactus primitives:

**Tool steps:**
- `the {tool} tool should be called`
- `the {tool} tool should be called at least {n} times`
- `the {tool} tool should be called with {param}={value}`

**Stage steps:**
- `the procedure has started`
- `the stage should be {stage}`
- `the stage should transition from {stage1} to {stage2}`

**State steps:**
- `the state {key} should be {value}`
- `the state {key} should exist`

**Completion steps:**
- `the procedure should complete successfully`
- `the stop reason should contain {text}`

**Iteration steps:**
- `the total iterations should be less than {n}`
- `the agent should take at least {n} turns`

### Custom Steps

Define custom steps in Lua for advanced assertions:

```lua
step("the research quality is high", function()
  local results = State.get("research_results")
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