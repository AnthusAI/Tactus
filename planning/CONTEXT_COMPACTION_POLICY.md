# Context Compaction Policy and Budgeting Hooks

## Purpose
Define a composable policy surface for Context compaction and pack budgeting that is deterministic, testable, and suitable for Context composition. This document clarifies how compaction and regeneration decisions are made and where custom implementations plug in.

## Goals
- Preserve a high-level DSL while making compaction behavior explicit and predictable.
- Keep pack-level budgets and context-level budgets coordinated.
- Enable custom compaction implementations without changing caller code.
- Support nested Contexts with budget propagation and regeneration.

## Policy Surface (High-Level)
Context policies provide the budgeting and compaction behavior. The current intent is:

- `input_budget`: Maximum token budget for the assembled prompt (system + history + user).
- `pack_budget`: Shared budget for Context packs; may be expressed in ratio or absolute tokens.
- `overflow`: Strategy for over-budget content. Current behavior assumes `compact` triggers regeneration/compaction when possible.
- `compactor`: Pluggable compaction implementation selected by name or inline config.
- `max_iterations`: Regeneration loop cap for shrinking retriever outputs.

These are defined in `ContextPolicySpec` and should remain the primary knobs for configuration.

## Budgeting Phases
1. **Pack Budget Allocation**
   - If a Context defines packs without explicit budgets, the pack budget is shared across packs.
   - Allocation respects:
     - Explicit `budget` per pack (reserves upfront)
     - `weight` per pack (proportional allocation)
     - `priority` per pack (tie-breaker for fractional remainder)
   - In explicit Contexts, shared pack budgets may be scaled across regeneration iterations.

2. **Retriever Budget Application**
- Pack budgets are converted to retriever constraints (mapped to `maximum_total_characters` with a 4x token heuristic).
   - When a pack budget is capped by an outer Context (nested pack), the nested retrieval should re-run under the cap.

3. **Context Budget Enforcement**
   - If total prompt exceeds `input_budget`, history is trimmed first, then system prompt is compacted if `overflow = compact`.

## Regeneration Loop
Regeneration is used to shrink pack outputs when budgets are tight:

- For default Contexts: retrievers can be re-run with progressively smaller budgets when `overflow = compact`.
- For explicit Contexts: shared pack budgets may be scaled per iteration, shrinking each retriever.
- For nested Contexts: the outer pack budget can cap the nested Context, and nested retrievers should re-run under the cap.

Regeneration should stop when either:
- The raw (pre-compaction) output is under the target budget, or
- `overflow` does not allow compaction, or
- `max_iterations` is reached.

## Expansion Loop
Expansion is used to grow pack outputs when budgets allow:

- If `policy.expansion` is configured and a retriever pack is under its target budget, the retriever is re-run with pagination (`offset` + `limit`) to fetch additional pages.
- Expansion stops when the pack reaches the target fill ratio, when a page returns fewer results than `limit`, or when `max_pages` is reached.

Expansion is intended to be deterministic and to reuse the same retriever configuration across pages, differing only by the pagination offset.

## Compactor Plugin Interface
Compactors are responsible for token-level shrinkage when outputs are too large.

Expected interface:
- Input: `CompactionRequest(text: str, max_tokens: int)`
- Output: `str` (compacted text)

The compactor implementation is selected via:
- `compactor = "name"` (lookup by name)
- `compactor = { type = "truncate" }` (inline config)

Compactors should be deterministic and side-effect free.

## Hook Points for Customization
- **Pack budgeting**: custom policies can define budgets with ratios, absolute caps, weights, and priorities.
- **Retriever compaction**: retrievers may re-run under tighter budgets rather than post-compaction.
- **Context compaction**: compactor plugin determines how textual output is reduced.

## Testing Expectations
All behaviors above should be covered by BDD and unit tests:
- Allocation by weight and priority for both default and explicit Contexts.
- Nested budget caps and regeneration loops.
- Template interpolation of pack content in explicit messages.
- History trimming and system compaction under `input_budget`.
