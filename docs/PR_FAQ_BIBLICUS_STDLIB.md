# PR-FAQ: Biblicus integration in the Tactus standard library (draft)

## Press release

Today we are introducing a new Tactus standard library module that integrates Biblicus text utilities directly into Tactus procedures. Developers can now call Biblicus-proven text primitives (extract, annotate, markup, slice, redact, link) from `.tac` workflows without leaving the Tactus execution model or re-implementing those behaviors. The integration shares the same DSPy-based model configuration as Tactus, so providers and models are configured once and used consistently across both projects.

This release focuses on a minimal, composable foundation: a `biblicus.text` module with deterministic behavior in mock mode, strong input validation, and BDD-first specifications. The module exposes a small, explicit API that mirrors Biblicus semantics while fitting Tactus's tool-oriented workflow patterns. Callers describe what they want returned; the markup mechanics stay under the hood. This creates a clear on-ramp for later work such as context packs and retrieval-augmented generation workflows, without committing to new DSL constructs prematurely.

## FAQ

### What problem does this solve?
Tactus users need high-quality, reusable text utilities that are already proven in Biblicus. Re-implementing those utilities in Tactus would create duplication, drift, and different behavior under the same name. This integration ensures a single source of truth for these text operations and aligns the AI stack so both projects use DSPy consistently.

### What is included in the first release?
- A new standard library module: `biblicus.text`.
- Lua-facing functions that call Biblicus text utilities with strict validation and deterministic outputs.
- BDD specs that document and verify behavior in Tactus standard library terms.
- Provider/model configuration reuse via DSPy underpinnings, matching Tactus conventions.
 - Simple usage: user messages describe the desired output; the markup details are handled internally.

### What is explicitly out of scope?
- Full knowledge base ingestion or retrieval pipelines.
- New DSL constructs such as `Corpus` or `ContextPack`.
- A Biblicus CLI inside Tactus.
- Production readiness claims for any RAG workflows.

### How does configuration work?
The module accepts model and provider configuration in the same shape as existing Tactus stdlib primitives (provider required, model optional depending on function), and passes those into Biblicus utilities that rely on DSPy. The configuration model stays in Tactus so that users do not need a parallel Biblicus configuration file for these calls.

### Why not add a new DSL construct for corpora now?
The first goal is to make Biblicus utilities available in a composable and minimal way. The standard library path allows us to validate ergonomics and usage patterns before committing to any new grammar constructs. If common usage proves that a first-class construct improves clarity, we can then propose it with evidence.

### How is this tested?
The module ships with BDD specs in `tactus/stdlib/tac/tactus/*.spec.tac` that serve as contracts. The specs are executed with `tactus stdlib test` and must pass before merge. Any changes in Biblicus-facing behavior require corresponding spec updates.

### What are the risks?
- API surface mismatch between Tactus stdlib and Biblicus utilities.
- Configuration drift if provider settings are not mapped consistently.
- Overloading the stdlib with too many options before usage is understood.

### How do we mitigate those risks?
- Keep the initial API minimal and mirrored to Biblicus semantics.
- Use explicit Pydantic models at the boundary for configuration and outputs.
- Enforce specs as contracts and require docs updates for each behavior.

### What comes next?
- Add context pack helpers (without new DSL syntax) to plug corpora into agent prompts.
- Explore a high-level `Corpus` construct if the standard library interface proves insufficient.
- Add end-to-end examples and real integration tests in `.tac` files.
