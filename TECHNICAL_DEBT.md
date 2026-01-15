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

## Policy: Keep Resolved Items Indefinitely

This document intentionally retains **Resolved** items indefinitely.

Rationale:
- We need a durable record of why changes were made and what debt they eliminated.
- It provides ready-to-use context for future Git commit messages and release notes (even though `CHANGELOG.md` is generated automatically).

---

## New Findings (2026-01-14)

### Resolved (2026-01-15): Eliminate compatibility parameter aliases (breaking)

**Goal:** Accept exactly one canonical name/shape per concept (except the explicit `Specification`/`Evaluation` singular convenience).

**Changes:**
- **Agent turn input:** standardize on `message` (remove legacy alternatives like `inject`).
- **Agent config:** reserve `tools` for **inline tool definitions** only; use `toolsets` for tool/toolset references (strings) and toolset expressions (filter dicts like `{name="plugin", include={...}}`).
- **Message history:** remove the `session` alias; use `message_history` only.

**CI/test follow-through (required to keep suite deterministic):**
- Ensure example BDD runner supplies `tool_paths` for plugin-backed examples.
- Ensure MCP fixture servers run with `cwd` set to repo root so `python -m tests.fixtures...` resolves under Behave temp directories.

**Files:** `tactus/core/dsl_stubs.py`, `tactus/dspy/agent.py`, `tactus/core/registry.py`, `tactus/core/runtime.py`, `tactus/testing/*`, `tests/testing/test_all_examples.py`, examples, docs.

### Resolved (2026-01-14): Runtime Bug — empty tool schemas become lists (breaks tool registration)

**Symptom:** `examples/71-mocking-temporal.tac` failed with `Toolset 'get_counter' not found` and was skipped in `tests/testing/test_all_examples.py`.

**Root cause:** `lua_table_to_dict({})` returns `[]` by design, and tool declarations currently do **not** normalize empty schemas back to `{}`. This produces tool specs like `input: []`, but the Lua tool adapter expects dict-like schemas and fails (e.g., `.items()` on a list), preventing toolsets from being registered.

**Why it matters:** This is a core-language correctness bug (empty schema should mean “no fields”), and it blocks multiple examples/tests and any user-authored tools with `input = {}`.

**Fix:** Normalize tool `input`/`output` schemas during DSL parsing so empty schemas are treated as empty objects, not arrays; remove the `71-mocking-temporal` skip.

**Files:** `tactus/core/dsl_stubs.py`, `tests/testing/test_all_examples.py`.

---

### Resolved (2026-01-14): DSL ergonomics — allow singular `Specification` / `Evaluation` blocks

**Goal:** Improve readability when there is only a single spec/eval block in a file without introducing broad compatibility shims.

**Change:** Support the singular forms:
- `Specification([[ ... ]])` as an alias for `Specifications([[ ... ]])`
- `Evaluation({ dataset = ..., evaluators = ... })` as an alias for `Evaluations({ ... })` (disambiguated from `Evaluation { runs = ..., ... }`)

**Policy note:** This is an explicit, narrow exception to the “no aliases” rule because it improves the core DSL ergonomics without duplicating data shapes or introducing ambiguous fallbacks.

**Files:** `tactus/core/dsl_stubs.py`, `tactus/validation/semantic_visitor.py`, `tests/testing/test_all_examples.py`, `examples/*.tac`, docs/snippets.

---

### Resolved (2026-01-14): BDD ergonomics — deterministic fuzzy output matching (non-breaking)

**Problem:** Real-model responses are inherently variable; strict string equality makes BDD specs brittle even when the behavior is correct.

**Fix:** Add deterministic fuzzy matching for scalar outputs with:
- Case-insensitive comparison (lowercased)
- Punctuation stripped
- Whitespace normalized
- Optional multi-match support: `any of ["hello", "hi", "hey"]`

**Files:** `tactus/testing/steps/builtin.py`, `docs/BDD_TESTING.md`, examples.

---

### Resolved (2026-01-14): Test Debt — script-mode agent mocking test skipped due to incorrect mock shape

**Symptom:** `tests/core/test_script_mode.py` skipped `test_script_mode_with_mock_agent` (“Agent name assignment interception not yet working for DSPy agents”).

**Root cause:** The test uses `Mocks { worker = { returns = ... } }`, which defines a *tool* mock, not an *agent* mock. Agent mocks use `tool_calls` + `message` (see examples). The skip reason appears to be a placeholder; the real issue is the test’s mock definition (and possibly missing wiring for script mode, depending on the call path).

**Fix:** Update the test to use the correct agent-mock structure (`tool_calls` + `message`) and unskip it.

**Files:** `tests/core/test_script_mode.py`.

---

### Resolved (2026-01-14): CI landmines — broker integration tests could hang

**Symptom:** `tests/broker/test_broker_integration.py::test_broker_events_emit_round_trip` stalled (UDS + TCP variants).

**Root cause:** UDS server used an asyncio server with an AnyIO stream handler signature mismatch; TCP server created a listener but never started serving in the context manager.

**Fix:** Implement explicit asyncio connection handlers for the UDS server and start `listener.serve(...)` as a background task for TCP. Normalize shutdown to tolerate expected `ClosedResourceError` / `ExceptionGroup` paths.

**Files:** `tactus/broker/server.py`.

---

### Resolved (2026-01-14): Autonomy tooling — enforce per-command timeouts in the full suite

**Problem:** A stalled subprocess could block the agent indefinitely.

**Fix:** Add a repo-local timeout wrapper and a `scripts/run_precommit_suite.sh` runner that enforces a 5-minute timeout per command (and uses `pytest-timeout` for individual tests).

**Files:** `scripts/timeout.py`, `scripts/run_precommit_suite.sh`.

---

### Remaining: Test harness gaps — IDE server tests are intentionally skipped

### Resolved (2026-01-14): Test harness — deterministic MCP example coverage (no skips)

**Symptom:** MCP examples were skipped in `tests/testing/test_all_examples.py` with “MCP testing not yet implemented”.

**Fix:** Wire MCP server configs through the BDD runner so MCP toolsets can be initialized in mocked CI runs using local fixture servers.
- Add `mcp_servers` plumbing: `TactusTestRunner` → Behave `environment.py` → `TactusTestContext` → `TactusRuntime`.
- Add local fixture MCP servers for `filesystem` + `brave-search` so `62-mcp-toolset-by-server` can run without Node.js or external APIs.
- Add `Specification([[ ... ]])` to `40-mcp-test` and `41-mcp-simple`.
- Remove the MCP skip in `tests/testing/test_all_examples.py` (MCP examples now run like any other example BDD spec).

**Files:** `tactus/testing/test_runner.py`, `tactus/testing/behave_integration.py`, `tactus/testing/context.py`, `tests/testing/test_all_examples.py`, `tests/fixtures/filesystem_mcp_server.py`, `tests/fixtures/brave_search_mcp_server.py`, `examples/40-mcp-test.tac`, `examples/41-mcp-simple.tac`, `examples/62-mcp-toolset-by-server.tac`.

**IDE server BDD feature:** `features/19_ide_server.feature` is tagged `@skip` because it requires launching real server processes and would block.
- **Action:** Add a testable/non-blocking mode for `tactus ide` (e.g., `--once`, `--timeout`, `--no-build`) so these scenarios can run headlessly and terminate. Remove the `@skip` tag once deterministic.

---

### Resolved (2026-01-14): Standardize results on `result.output` only (breaking)

We now have a single, explicit, uniform result surface:

```lua
result.output  -- string or structured data
result.usage   -- {prompt_tokens, completion_tokens, total_tokens}
result.cost()  -- {total_cost, prompt_cost, completion_cost}
```

**Mandate:** No backward compatibility. No `result.value`, no aliases, no duplicated fields.

**Implementation locations:** `tactus/dspy/agent.py`, `tactus/protocols/result.py`, plus Lua-facing wrappers/tests/examples.

**Related historical tracking:** “Result usage/message history exposure” → https://github.com/AnthusAI/Tactus/issues/10 (closed)

---

### Resolved (2026-01-14): Test isolation — example suite “suite-only” failure for `60-tool-sources`

`tests/testing/test_all_examples.py` included a hard-coded skip for `60-tool-sources` due to suite-only failures (passed alone, failed in full run) that surfaced as `Toolset 'log' not found`.

**Root cause:** Lua tool signature generation depended on Lua table iteration order. When the optional parameter happened to be encountered before a required parameter, `inspect.Signature(...)` raised `ValueError: non-default argument follows default argument`, preventing the toolset from registering.

**Fix:** Make Lua tool signature generation deterministic and always order required params before optional params.

**Files:** `tactus/adapters/lua_tools.py`, `tests/testing/test_all_examples.py`.

---

## Active Technical Debt (Prioritized for Early Breaking Changes)

_(No currently-active items in this category.)_

---

## Active Technical Debt (Non-Breaking Correctness / Robustness)

These items improve correctness, robustness, and testability without requiring a user-facing language redesign.

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
1. Fix the empty tool-schema normalization bug; unskip and pass `examples/71-mocking-temporal.tac` under mocked BDD.
2. Unskip and fix the script-mode mock-agent test (test-only fix).
3. Remove example-suite special-casing by fixing state isolation (`60-tool-sources`).
4. Make MCP tests deterministic and remove MCP skips.
5. Make IDE server tests headless and non-blocking; remove `@skip`.
6. Enforce breaking-result semantics (`result.value` only) and remove any legacy result surfaces.
