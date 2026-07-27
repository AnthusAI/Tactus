# Agent Primitive (Human + LLM Quick Reference)

This document is a canonical reference for how to *think about* and *use* the Tactus **Agent** primitive.

If you are writing docs, examples, or AI assistance prompts, copy from here.

## One-sentence definition

An **Agent** is Tactus's stateful, multi-turn runtime for LLM-driven work: it can take turns, call tools, and build up conversation history across turns.

## Agent vs Model

Use an **Agent** when you want:

- multi-turn reasoning and dialogue
- tool use (search, file IO, APIs)
- iterative planning and refinement
- "open-ended" work where outputs emerge across turns

Use a **Model** when you want:

- stateless inference (classification, extraction, scoring)
- crisp input/output contracts
- outputs that drive deterministic control flow

Rule of thumb:

- Models produce signals.
- Procedures make decisions.
- Agents do open-ended work.

## The canonical agent call pattern

Agents are called like functions.

The callable form is the canonical API. Use `agent({message = "..."})`; do not
build new workflows around the legacy `.turn()` spelling.

```lua
my_agent = Agent {
  model = "openai/gpt-4o-mini",
  system_prompt = "You are helpful and concise.",
  tools = { /* ... */ }
}

Procedure {
  function(input)
    my_agent({message = "Do the task."})
    -- In most patterns, the procedure uses Tool tracking, state, or outputs
    -- rather than relying on free-form text.
  end
}
```

Model naming note:

- Preferred: `model = "provider/model"` (LiteLLM format, e.g. `"openai/gpt-4o-mini"`).
- Supported: `provider = "openai", model = "gpt-4o-mini"` (Tactus will normalize to `"openai/gpt-4o-mini"`).

Agents are non-deterministic by nature; you typically structure correctness around:

- tools (and tool results)
- explicit procedure state
- bounded loops and stopping conditions
- specifications (BDD) that assert observable behavior

## Request timeout, prewarming, and lifecycle telemetry

Set `request_timeout` on an Agent when provider requests need a bounded timeout.
The same value applies to streaming and non-streaming calls:

```lua
assistant = Agent {
  model = "openai/gpt-4o-mini",
  request_timeout = 60,
}
```

Python hosts that keep workers warm can initialize the complete DSPy/LiteLLM
stack without sending an inference request:

```python
from tactus.dspy import prewarm_agent_runtime

prewarm_agent_runtime(
    "openai/gpt-4o-mini",
    request_timeout=60,
)
```

Agents reuse a matching prewarmed model client and adapter. Runtime integrators
can observe supported `AgentLifecycleEvent` records through the normal log
handler or an Agent's `lifecycle_hooks`. Events cover agent preparation, LM
initialization, provider dispatch, the first streamed chunk, and provider
completion. `provider_request_started` includes the rendered prompt context so
integrations can capture it without replacing private Agent methods.

Agents query their chat recorder for mid-run operator steering by default.
Directly driven interactive agents can disable that remote check when each
turn already supplies the latest user message:

```lua
assistant = Agent {
  model = "openai/gpt-4o-mini",
  steering_enabled = false,
}
```

## Per-turn capability control (important)

Tactus supports per-call overrides so you can change an agent's capabilities on a specific turn.

Example: "summarize results" turns should not be allowed to call tools.

```lua
-- Full tools turn
researcher({tools = {search, fetch, done}})

-- Summarize with no tools
researcher({message = "Summarize the tool results above.", tools = {}})
```

This is a key safety/reliability technique:

- tool call -> summarize -> tool call -> summarize -> done

## Dynamic system prompts (templates + per-turn override)

The agent’s `system_prompt` string is **re-rendered every turn** using [`TemplateResolver`](../tactus/core/template_resolver.py) markers:

- **`{params.*}`** — values from the **call** that are not reserved keys (`message`, `tools`, `temperature`, `max_tokens`, `system_prompt`). For example, `my_agent({ message = "Hi", topic = "bugs" })` exposes `{params.topic}`.
- **`{state.*}`** — procedure `State` (e.g. `{state.still_needed}` for a checklist the procedure updates in Lua before each turn).
- **`{prepared.*}`**, **`{context.*}`**, **`{env.*}`** — as documented in the template resolver.

You can also **replace the template for one turn** (still resolved the same way):

```lua
my_agent({
  message = "Continue.",
  system_prompt = "You are a focused reviewer.\n\nContext: {params.topic}\nOpen issues: {state.still_needed}",
})
```

Use this when building the whole instruction string in procedure code is clearer than a single static `Agent { system_prompt = ... }` block.

## The testing story: mock agents in CI

In CI, you usually do not want to call a real LLM. You want deterministic behavior.

Use `Mocks { ... }` to mock an agent's responses and tool calls.

```lua
Mocks {
  researcher = {
    tool_calls = {
      {tool = "search", args = {query = "tactus model primitive"}},
      {tool = "done", args = {reason = "Found the docs"}}
    },
    message = "Completed research"
  }
}
```

Run specs in mock mode:

```bash
tactus test path/to/file.tac --mock
```

Specs should assert your orchestration logic:

- the right tools were called
- control flow terminates (done called, loop exits)
- outputs/state are correct

## LLM-facing "Do / Don't"

Do:

- keep deterministic control flow in Procedures
- use tools for structured observable behavior
- use per-turn tool restrictions for safety and reliability
- use mocks for CI and specs that assert tool usage and outputs

Don't:

- don't build correctness around free-form text unless you validate it
- don't rely on an agent "remembering" state; store state explicitly
