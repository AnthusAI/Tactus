# Technical Debt: SPECIFICATION.md vs Implementation

**Created:** 2026-01-08
**Source:** Audit comparing SPECIFICATION.md against actual code and examples

---

## Policy: Intentional Breaking Changes

Tactus is early-stage. We **prefer breaking changes** over compatibility shims when they improve elegance, consistency, safety, or long-term maintainability.

Guidelines:
- **No backward compatibility**: no aliases, no duplicated fields, no “accept both” parameter support, no silent fallbacks.
- If we standardize on a single shape (e.g., `result.output`), we **remove** any legacy access patterns.
- When a breaking change is made, update `SPECIFICATION.md`, `IMPLEMENTATION.md`, and examples in the same sweep (and keep the test suite passing continuously).

## Active Technical Debt (Prioritized for Early Breaking Changes)

## Active Technical Debt (Non-Breaking Correctness / Robustness)

These items improve correctness, robustness, and testability without requiring a user-facing language redesign.

### IDE Server BDD Feature Coverage (blocked by @skip)

`features/19_ide_server.feature` is tagged `@skip` because it requires launching real server processes and would block/flake in CI.

**Goal:** Make these scenarios deterministic and non-blocking so the feature file can run headlessly in CI.

**Candidate approach:**
- Add a test mode for `tactus ide` (e.g., `--once`, `--timeout`, `--no-build`) so it starts, serves one request (or runs a small healthcheck), and exits cleanly.
- Remove the `@skip` tag once deterministic.

### HITL Message Classifications (open issue)

Tag every message with a `humanInteraction` classification to support IDE/CLI filtering, audit trails, and clearer HITL UX.

Tracking: https://github.com/AnthusAI/Tactus/issues/3 (open)

### Agent Hooks (open issue)

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

Tracking: https://github.com/AnthusAI/Tactus/issues/13 (open)

---

## Roadmap Decisions (Major Features)

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

## Reconciled With GitHub Issues (Closed = Ignored)

The following items were already filed as GitHub issues and are **closed**. Per project planning policy, we treat them as resolved and do not prioritize them here:

- Toolset declaration syntax spec drift → https://github.com/AnthusAI/Tactus/issues/5 (closed)
- Spec: agent callable uses `initial_message` not `message` → https://github.com/AnthusAI/Tactus/issues/6 (closed)
- Spec: implemented template namespaces → https://github.com/AnthusAI/Tactus/issues/7 (closed)
- Spec: summarization prompts are logged-only → https://github.com/AnthusAI/Tactus/issues/8 (closed)
- Checkpoint inspection helpers → https://github.com/AnthusAI/Tactus/issues/9 (closed)
- Result usage/message history exposure → https://github.com/AnthusAI/Tactus/issues/10 (closed)
- Named checkpoints → https://github.com/AnthusAI/Tactus/issues/11 (closed)
- System.alert primitive → https://github.com/AnthusAI/Tactus/issues/12 (closed)
- HITL message classifications (earlier ticket) → https://github.com/AnthusAI/Tactus/issues/4 (closed)

Note: HITL message classifications are currently tracked in https://github.com/AnthusAI/Tactus/issues/3 (open); an earlier similarly named ticket (#4) is closed.

---

## Execution Plan (Keep Suite Passing)

Order of operations (highest leverage first):
1. Make IDE server tests headless and non-blocking; remove `@skip`.
2. Implement HITL message classifications end-to-end (runtime + IDE + CLI).
3. Implement agent hooks (prepare/filter/retry) or explicitly remove them from spec.
4. Make roadmap decisions on async/durable execution and either implement or remove from spec.
