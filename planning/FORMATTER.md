# Formatter Roadmap (Lua DSL)

## Goal

Provide a stable formatter for `.tac` / `.lua` that preserves meaning, keeps comments, and converges to a single canonical style. This should be developed BDD-first with idempotence guarantees from the start.

## Milestones

### Milestone A: Semantic Indentation Formatter

Primary requirement:
- Enforce 2-space indentation based on syntactic structure (not lexical heuristics).

Scope:
- Reindent lines using the ANTLR token stream / parse result.
- Preserve existing line breaks and token spelling.
- Preserve comments and avoid rewriting inside multi-line comments/strings.
- Idempotent output (formatting twice yields the same file).

Non-goals:
- Line wrapping, alignment, or spacing normalization beyond indentation.

### Milestone B: Canonical Pretty Printer

Primary requirement:
- Black-like canonical formatting beyond indentation.

Scope (incremental):
- Normalize spaces around operators, commas, braces/parens.
- Canonical table formatting (inline vs multiline decisions).
- Stable line breaking within a configured line length.
- Robust comment attachment and placement.
- Preserve (or consistently normalize) string literal forms where safe.

Non-goals:
- Formatting arbitrary Lua “perfectly” in the first iteration; prioritize the Tactus DSL subset and expand.

## Test Strategy (BDD + Pytest)

- Behave scenarios:
  - `tactus format` rewrites indentation to 2 spaces.
  - `tactus format --check` fails when changes are needed.
  - Idempotence: running `tactus format` twice does not change output.
- Pytest unit tests:
  - Idempotence at the formatter API level.
  - Representative fixtures for nested blocks and tables.
  - Negative tests (invalid input should not be formatted).

