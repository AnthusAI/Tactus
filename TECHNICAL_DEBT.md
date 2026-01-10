# Technical Debt: SPECIFICATION.md vs Implementation

**Created:** 2026-01-08
**Source:** Audit comparing SPECIFICATION.md against actual code and examples

---

## Category 1: Update Spec to Match Reality (Documentation Fixes)

These items are working correctly in the implementation. The spec just documents the wrong syntax or behavior.

### Toolset Declaration Syntax

Toolsets group multiple tools together. The spec shows function-call syntax, but the implementation uses Lua's syntactic sugar for function calls with string arguments.

| Spec (Wrong) | Reality (Correct) |
|--------------|-------------------|
| `toolset("math_tools", {...})` | `Toolset "math_tools" {...}` |

**Why it matters:** The actual syntax is more DSL-like and consistent with other Tactus declarations.

**Files to update:** SPECIFICATION.md line 1897

---

### Agent Callable Parameter Name

When calling an agent with an initial message, the parameter name differs between spec and implementation.

| Spec (Wrong) | Reality (Correct) |
|--------------|-------------------|
| `worker({message = "..."})` | `worker({initial_message = "..."})` |

**Why it matters:** Users following the spec will pass a parameter that gets ignored.

**Files to update:** SPECIFICATION.md line 2235

---

### Template Variable Namespaces

Template variables let you inject dynamic values into prompts like `{input.topic}`. The spec documents six namespaces, but only two are implemented.

| Namespace | Spec Says | Reality |
|-----------|-----------|---------|
| `{input.*}` | Supported | **Working** |
| `{state.*}` | Supported | **Working** |
| `{output.*}` | Supported | Not implemented |
| `{context.*}` | Supported | Not implemented |
| `{prepared.*}` | Supported | Not implemented |
| `{env.*}` | Supported | Not implemented |

**Why it matters:** Users trying to use `{env.API_KEY}` or `{prepared.data}` in prompts will get raw text instead of substituted values.

**Files to update:** SPECIFICATION.md lines 843-856 - mark unimplemented namespaces as "Planned"

---

### Summarization Prompts Behavior

The spec says `return_prompt`, `error_prompt`, and `status_prompt` trigger additional agent turns to generate summaries. In reality, these values are just logged - no agent interaction happens.

**Spec claims:**
> "Injected when the procedure completes successfully. The agent does one final turn to generate a summary, which becomes the return value."

**Reality:** The prompt is logged but no agent turn is executed.

**Why it matters:** Users expecting automatic summarization will be confused when it doesn't happen.

**Files to update:** SPECIFICATION.md lines 427-492 - clarify actual behavior

---

## Category 2: Small Feature Gaps

These are minor features documented in the spec that could be implemented with small code changes.

### Checkpoint Inspection Methods

Implemented in `tactus/primitives/step.py` (`Checkpoint.exists(position)`, `Checkpoint.get(position)`).

---

### Result Object with Usage Statistics

We want a standard Result object with response data + token usage + cost:

```lua
result.value   -- string or structured data
result.usage   -- {prompt_tokens, completion_tokens, total_tokens}
result.cost()  -- {total_cost, prompt_cost, completion_cost}
```

**What exists now:** `TactusResult` returned by `Agent()` (breaking change: use `result.value`)

**Intentionally not implemented (YAGNI for now):**
- `result.new_messages()`
- `result.all_messages()`

**Why it matters:** Users can't track token usage or costs per-call, which is important for optimization and budgeting.

**Implementation locations:**
- `tactus/dspy/agent.py`
- `tactus/protocols/result.py`
- `tactus/protocols/cost.py`

---

## Category 3: Medium Features (Backlog)

### Named Checkpoints

Convert from position-based to named checkpoints:

```lua
-- Would allow:
local data = Step.run("fetch_data", function() return api.fetch() end)

-- And later:
Checkpoint.clear_after("fetch_data")  -- Rerun from this point
```

**Value:** Better debugging, selective replay, clearer execution traces

**Trade-off:** More complex checkpoint management, potential for name collisions

---

### System.alert() Primitive

A non-blocking alert system for operational monitoring:

```lua
System.alert({
    message = "Memory usage high",
    level = "warning",  -- info, warning, error, critical
    source = "batch_processor",
    context = {memory_mb = 1500}
})
```

**Value:** Procedures can emit alerts without blocking, integrates with monitoring systems

**Difference from Human.notify:** System alerts are for ops/devops, Human.notify is for workflow participants

---

### HITL Message Classifications

Tag every message with a `humanInteraction` classification:

- `INTERNAL` - Hidden from human UI (agent reasoning, tool calls)
- `CHAT` / `CHAT_ASSISTANT` - Normal conversation
- `PENDING_APPROVAL` / `PENDING_INPUT` / `PENDING_REVIEW` - Waiting for human
- `RESPONSE` - Human's response to a pending request
- `ALERT_*` - System alerts at various severity levels

**Value:** Better UI filtering, audit trails, separation of concerns

---

### Agent Hooks

The spec describes agent lifecycle hooks that aren't implemented:

```lua
worker = Agent {
    prepare = function()
        -- Runs before each turn, returns data for {prepared.*} templates
        return {file_contents = File.read("context.txt")}
    end,

    filter = {
        class = "TokenBudget",
        max_tokens = 120000
    },

    response = {
        retries = 3,
        retry_delay = 1.0
    }
}
```

**Value:** More control over agent behavior without modifying core code

---

## Category 4: Major Features (Roadmap Decisions)

These are significant features that need explicit prioritization decisions.

### Async/Durable Execution Context

The spec describes a full AWS Lambda durable execution system:

- `async = true` for non-blocking procedure invocation
- Automatic checkpointing with Lambda SDK
- HITL waits that suspend Lambda (zero compute cost while waiting)
- Executions that can span up to 1 year

**Current state:** Completely unimplemented. The spec has detailed architecture diagrams for something that doesn't exist.

**Decision needed:** Is this on the roadmap? If not, remove from spec. If yes, when?

---

### Procedure.spawn and Async Primitives

Async procedure management:

```lua
local handle = Procedure.spawn("researcher", {query = "..."})
local status = Procedure.status(handle)
local result = Procedure.wait(handle, {timeout = 300})
Procedure.wait_any(handles)
Procedure.wait_all(handles)
```

**Dependency:** Requires async execution context (4.1)

---

### Session Primitives

Direct manipulation of conversation history:

```lua
Session.append({role = "user", content = "..."})
Session.inject_system("Additional context...")
Session.clear()
local history = Session.history()
```

**Question:** Does this overlap with existing MessageHistory functionality?

---

### Graph Primitives

Tree search and MCTS support:

```lua
local root = GraphNode.root()
local current = GraphNode.current()
local child = GraphNode.create({value = 0.5})
```

**Question:** Is this needed for current use cases?

---

## Recommended Action Plan

### Phase 1: Documentation Cleanup
Fix all Category 1 items in SPECIFICATION.md. Mark Category 4 features as "Planned/Future" rather than documenting them as if they exist.

### Phase 2: Decide on Backlog
Review Category 2 and 3 items. Which ones actually matter for current users?

### Phase 3: Roadmap Category 4
Make explicit decisions about major features. Either commit to building them or remove from spec.
