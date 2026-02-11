# Tactus Examples (Spec Suite)

This directory is now a **testing-only specification suite**. Tutorial and learning examples live in the separate repo: https://github.com/AnthusAI/Tactus-examples.

The definitive list of examples under test is tracked in `examples/manifest.yml` and consumed by `tests/testing/test_all_examples.py`. If you add or remove an example, update the manifest and this README together.

## Running examples

- Validate a single example: `tactus validate examples/04-basics-simple-agent.tac`
- Run BDD specs with mocks: `tactus test examples/20-bdd-complete.tac --mock`
- Evaluate with mocks: `tactus eval examples/30-eval-simple.tac --runs 5 --mock`

## Curated coverage map (why each is kept)

- **Basics** – core DSL and agent primitives: `01-basics-hello-world.tac`, `02-basics-simple-logic.tac`, `03-basics-parameters.tac`, `04-basics-simple-agent.tac`, `05-basics-multi-model.tac`, `06-basics-streaming.tac`
- **Features** – state, history, structure, tool usage: `10-feature-state.tac`, `11-feature-message-history.tac`, `12-feature-structured-output.tac`, `13-feature-session.tac`, `14-feature-per-turn-tools.tac`, `15-feature-local-tools.tac`, `16-feature-toolsets-advanced.tac`, `17-feature-toolsets-dsl.tac`, `18-feature-lua-tools-inline.tac`, `19-feature-direct-tool-calls.tac`
- **BDD specs** – representative specification flows: `20-bdd-complete.tac`, `21-bdd-passing.tac`, `22-bdd-fuzzy-matching.tac`
- **Evaluations** – eval runner + datasets: `30-eval-simple.tac`, `33-eval-thresholds.tac`, `34-eval-dataset.tac`, `35-eval-trace.tac`, `36-eval-advanced.tac`
- **Models & MCP** – model plumbing and MCP servers: `39-model-simple.tac`, `40-mcp-test.tac`, `41-mcp-simple.tac`
- **Sub-procedures & durability** – procedure composition and checkpoints: `43-sub-procedure-simple.tac`, `44-sub-procedure-composition.tac`, `46-checkpoint-explicit.tac`, `48-script-mode-simple.tac`
- **Inputs & file I/O** – parameter shapes and file adapters: `50-inputs-showcase.tac`, `52-file-io-basics.tac`, `54-json-file-io.tac`, `55-parquet-file-io.tac`, `57-excel-file-io.tac`
- **Tools & integrations** – tool discovery and broker flows: `60-tool-sources.tac`, `62-mcp-toolset-by-server.tac`, `64-require-modules.tac`, `66-host-tools-via-broker.tac`
- **Domain / mocking** – Biblicus + mocking coverage: `68-biblicus-text-extract.tac`, `70-mocking-static.tac`, `72-mocking-conditional.tac`, `74-biblicus-text-redact.tac`
- **HITL & control loop** – end-to-end HITL flows: `90-hitl-simple.tac`, `91-control-loop-demo.tac`, `93-test-ide-hitl.tac`, `95-agent-hitl.tac`
- **Context & dependencies** – elasticity and task dependencies: `96-context-elasticity-min.tac`, `97-task-deps-biblicus.tac`
- **Checkpoint/resume regression probes** – deterministic resume coverage: `test-resume-basic.tac`, `test-resume-llm.tac`, `test-resume-timeout.tac`
- **Support modules** – shared Lua helpers used by examples: `helpers/math_module.tac`, `helpers/product.tac`, `helpers/string_module.tac`, `helpers/sum.tac`, `helpers/text_tools.tac`

## Maintenance checklist

1) Add/update the entry in `examples/manifest.yml`  
2) Keep this README section in sync (coverage rationale)  
3) If behavior changes, update any dependent docs and rerun the relevant tests (`pytest tests/testing/test_all_examples.py -k <example>` or `npm test` for Behave suites).  
