# Conversation History Transforms Implementation Summary

## Overview
Conversation history grows quickly in real workflows. These APIs let you trim, rewind, and slice it in a predictable way. The design separates read-only views from state-changing edits so you can inspect safely and mutate only when you intend to.

### Read-only views (no mutation)
```lua
-- Peek without changing stored history
local recent = MessageHistory.tail(4)
local budgeted = MessageHistory.tail_tokens(800)
local first = MessageHistory.head(2)
```

### Mutations (state-changing)
```lua
-- Keep only the system preamble
MessageHistory.reset({keep = "system_prefix"})

-- Trim to a fixed size
MessageHistory.keep_tail(6)

-- Rewind to a checkpoint
local checkpoint_id = MessageHistory.checkpoint("draft")
-- ... more turns ...
MessageHistory.rewind_to(checkpoint_id)
```

### Why the split matters
Views help you inspect what’s there without side effects. Mutations let you intentionally reshape what future agent calls will see. That makes history management safe, predictable, and easy to reason about in Tactus code.

## Goals Implemented
- MessageHistory now supports mutation and query operations for reset/head/tail/rewind/slice.
- New filter helpers are available in the DSL for declarative history views.
- Token budgeting uses a deterministic heuristic by default (no model-specific tokenizer yet).
- The changes are covered by BDD and unit tests.

## DSL API (Current)
### MessageHistory mutations
- `MessageHistory.reset({keep = "system_prefix" | "system_all" | "none"})`
- `MessageHistory.rewind(n)`
- `MessageHistory.rewind_to(id_or_checkpoint)`
- `MessageHistory.keep_head(n)`
- `MessageHistory.keep_tail(n)`
- `MessageHistory.keep_tail_tokens(max_tokens, opts)`

### MessageHistory queries
- `MessageHistory.head(n)`
- `MessageHistory.tail(n)`
- `MessageHistory.slice({start = i, stop = j})`
- `MessageHistory.tail_tokens(max_tokens, opts)`
- `MessageHistory.checkpoint(name?) -> id`

### Options (Current Behavior)
- `opts` is accepted by the API but only `max_tokens` is used today.
- Token budgeting uses the existing deterministic heuristic (~4 characters per token).
- Model-specific tokenizers are not wired yet; this is a known follow-up.

## Message Model Enhancements
- Each message now receives:
  - `id` (monotonic int)
  - `created_at` (ISO timestamp)
These fields are injected on append and on serialization where missing.

## Token Counting Strategy
- Default: deterministic approximation (4 chars per token, plus small overhead).
- No model-specific token counting is implemented yet.

## Implementation Notes
### Core primitives
- `MessageHistory.replace(messages)` added to allow in-place history mutations.
- `MessageHistory.reset`, `head`, `tail`, `slice`, `keep_head`, `keep_tail`,
  `tail_tokens`, `keep_tail_tokens`, `rewind`, `checkpoint`, and `rewind_to` added.
- Metadata is assigned in `MessageHistoryManager` with a monotonic id and timestamp.

### Filters
New DSL helpers:
- `filters.first_n(n)`
- `filters.head_tokens(max_tokens)`
- `filters.tail_tokens(max_tokens)`
- `filters.system_prefix()`

### Docs and Examples
- `SPECIFICATION.md` updated with new API and filters.
- `IMPLEMENTATION.md` updated with new feature list.
- New example: `examples/11-feature-message-history-transforms.tac`.

## Open Questions
- Should token counting support explicit model-specific tokenizers?
- Should `system_prefix` be the only reset mode, or should we add more policies?
- Do we want a procedure-level default tokenizer setting?
- How should message ids be backfilled for pre-existing histories?

## Non-Goals
- No agent-specific tokenizer inference without explicit configuration.
- No automatic summarization or compression.
- No changes to provider SDK dependencies.

## Tests Added
- BDD: `features/67_message_history_transforms.feature`
- BDD: extended `features/30_session_filters.feature`
- Unit: `tests/primitives/test_message_history_primitive.py`
- Unit: `tests/core/test_message_history_manager.py`
