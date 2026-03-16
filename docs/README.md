# Tactus Docs Index

This folder contains design notes, guides, and reference docs for Tactus.

If you are new, start with the quick references and runnable examples first.

## For users (most common)

- `README.md` (repo root): overview + entry points
- `SPECIFICATION.md`: the language reference (DSL spec)
- Model primitive:
  - `docs/model-primitive.md` (quick reference)
  - `docs/model-training-walkthrough.md` (hands-on: train/eval/run)
- Agent primitive:
  - `docs/agent-primitive.md` (quick reference)
- Testing:
  - `docs/BDD_TESTING.md` (Gherkin specs, mock mode, deterministic CI)
- Tools:
  - `docs/TOOLS.md` (tooling + MCP integration)
- Durability:
  - `docs/DURABILITY.md` (checkpoint/replay design; includes historical snippets, but links to canonical patterns)
- Configuration:
  - `docs/CONFIGURATION.md` (config cascade, sandbox config, registry env vars)

## For AI assistants / automated tooling

- `llms.txt` (repo root): canonical patterns and "do/don't" guidance
- `docs/model-primitive.md`: canonical Model syntax + registry + mocking patterns
- `docs/agent-primitive.md`: canonical Agent mental model + mocking patterns

## For contributors / implementers

- `docs/IMPLEMENTATION.md`: architecture and current status
- `docs/SANDBOXING.md`: threat model and sandbox design
- `docs/MODEL_PRIMITIVE_STATUS.md`: implementation status and milestones
- `docs/MODEL_PRIMITIVE_PLAN.md`: roadmap notes (contains historical sketches; canonical syntax lives elsewhere)

