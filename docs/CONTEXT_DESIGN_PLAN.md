# Context Design Plan (Biblicus Integration)

## Goal
Define a first-class `Context` construct in Tactus that unifies:
- context planning (what we want),
- context assembly (what we send), and
- context compaction (how we fit budgets),

while keeping everything Pydantic-validated and composable.

## Core Decisions (Current)
1) **Context is the master construct**
   - `Context` encapsulates policy, message plan, and computed runtime history.
   - It is the only user-facing abstraction for context packing in Tactus.

2) **Context is composable and recursive**
   - Any object that can contribute to LLM input is represented as a `Context` node.
   - Messages are leaf nodes; retrievers and corpora are `Context`-producing nodes.
   - A `Context` can contain messages and other Context nodes.

3) **Context is the object passed to `Agent.context`**
   - It is computed just-in-time for each model call.
   - It can be re-computed with new budgets or policies.

4) **History insertion rules**
   - If `messages` is omitted: use the default assembly policy (system → packs → history → user).
   - If `messages` is provided: no implicit history insertion.
   - `history()` must be included explicitly when `messages` is specified.
   - Default guidance: insert `history()` between the last system message and the first user message.

5) **Context packing and compaction**
   - Budgeting is automated and driven by policy.
   - Compaction is implemented via pluggable classes/functions (not hard-coded named strategies).
   - Retrievers can participate in budget adjustment (e.g., re-query with smaller output).

6) **Template interpolation**
   - Context packs are interpolated using dot syntax:
     - `{context.support_search}`
   - No special colon syntax; keep templates consistent with existing interpolation rules.

## DSL Shape (Target)

Example with explicit message plan:

```
support_context = Context {
  policy = {
    input_budget = { ratio = 0.5 },
    pack_budget = { default_ratio = 0.2 },
    overflow = "compact"
  },
  messages = {
    system "You are a support agent.",
    context support_search,
    system template("Use this:\n{context.support_search}"),
    history(),
    user template("Question: {input.question}")
  }
}
```

Example with implicit/default message plan:

```
support_context = Context {
  policy = { input_budget = { ratio = 0.5 } },
  packs = { support_search }
}
```

## Pydantic Model Plan
- `ContextSpec`
  - `policy: ContextPolicy`
  - `messages: list[ContextMessage] | None`
  - `packs: list[ContextRef] | None`
  - Validation rules for explicit vs implicit history behavior.

- `ContextMessage` (Union)
  - `SystemMessage`, `UserMessage`, `AssistantMessage`
  - `TemplateMessage`
  - `ContextInsert` (for nested contexts or retrievers)
  - `HistoryInsert` (from `history()`)

- `ContextPolicy`
  - `input_budget` (ratio or absolute token cap)
  - `pack_budget` (default per-pack ratio or caps)
  - `overflow` (e.g., "compact" / "truncate" / custom)
  - `compactor` (plugin reference + config)

- `CompactorSpec`
  - Pydantic-validated plugin configuration.
  - Resolved via registry; supports custom user implementations.

## Open Questions
- Whether `Compactor` should be a first-class DSL construct (`compactor = Compactor { ... }`) or
  a policy field with a plugin reference. (Leaning: make it a first-class construct.)
- How to expose token measurement utilities in the DSL or runtime API for diagnostics.

## Non-Goals (for now)
- High-level analysis recipes (topic modeling, markov, etc.) remain tools, not language primitives.
- RAG usage will be built via Context + Retriever + Corpus, not separate DSL syntax.

## Next Implementation Steps
1) Add Pydantic schema types in `tactus/core` or `tactus/primitives` (consistent with existing patterns).
2) Update parser/AST to support `Context`, `Corpus`, `Retriever`, and `history()`.
3) Implement runtime assembly for Context with implicit/explicit history rules.
4) Add validation warnings for explicit `messages` missing `history()`.
5) Add BDD specs for default and explicit behavior, plus compaction plugin wiring.

