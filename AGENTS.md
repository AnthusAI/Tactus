# Instructions for Coding Agents

This document provides guidelines for AI coding agents working on the Tactus project.

## Brand Theme & Visual Design Policies

*   **Flat Design Only**:
    *   No gradients.
    *   No drop-shadows (unless totally flat/hard).
    *   No borders/outlines on containers or regions.
*   **Contrast & Separation**:
    *   Avoid thin lines (hrules, borders) for separating regions.
    *   Use **varying background colors** on flat rectangles with rounded corners to indicate regions and groupings.
    *   Use contrast carefully; avoid high contrast.
        *   Background black should not be fully black (e.g., use dark gray).
        *   Foreground white should not be fully white.
        *   Use a limited set of official colors: "not-black", "not-white", and 2-3 "muted" colors.
*   **Color System**:
    *   Themes use **Radix Colors** (Cool, Neutral, Warm).
    *   Support both Light and Dark modes.
*   **Typography & Layout**:
    *   Refined elegance, modern Bauhaus-inspired, Apple's modern minimalist Art Deco.
*   **Animations**:
    *   Subtle animation effects are encouraged.
    *   **NO CSS animations** (like Framer Motion) for components that feature in Babulus videos.
    *   Use **frame-parameterized animations**: Animations must be driven by a `frame` parameter so they can be rendered deterministically in videos.
*   **Development Workflow**:
    *   Refer to **Shadcn UI** for default UX design patterns.
    *   Provide examples of basic visual elements in **Storybook stories**.
    *   Do research into best practices for specific tasks.

## Pre-Commit Checklist

**CRITICAL**: Before committing any changes, you MUST:

1. **Wait for human approval** - DO NOT COMMIT until the human user has tested and approved your changes
2. **Run the complete test and linting suite**:

```bash
# 1. Run unit tests
pytest tests/ -x -k "not test_real_execution"

# 2. Run BDD behavior tests
behave --summary

# 3. Check code style with ruff (no uncommitted code should have ruff errors)
ruff check .

# 4. Format code with black
black tactus tactus-ide/backend features/steps tests

# 5. Verify all checks pass again
ruff check .
black tactus tactus-ide/backend features/steps tests --check
```

Only commit when:
- The human user has explicitly approved the changes
- ALL of the above checks pass

Do not skip this step or commit before getting approval and running these checks.

## Reference Documentation

- **[SPECIFICATION.md](SPECIFICATION.md)**: The official specification for the Tactus domain-specific language. Refer to this document for the definitive guide on DSL syntax, semantics, and behavior.
- **[IMPLEMENTATION.md](IMPLEMENTATION.md)**: Maps the specification to the actual codebase implementation. Shows where each feature is implemented, what's complete, and what's missing relative to the specification. Use this to understand the current implementation status when working on features.

## Multi-Model and Multi-Provider Support

**IMPORTANT**: Tactus now supports multiple LLM providers and models:

- **Providers**: `openai` and `bedrock` are supported
- **Provider is REQUIRED**: Every agent must specify `provider:` (either directly or via `default_provider:` at procedure level)
- **Multiple models**: Different agents can use different models (e.g., GPT-4o, GPT-4o-mini, Claude 3.5 Sonnet)
- **Model parameters**: Supports model-specific parameters like `temperature`, `max_tokens`, `openai_reasoning_effort`

**Provider-Specific Dependencies**:
- **DO NOT add provider-specific SDK dependencies** (e.g., `openai`, `anthropic`, etc.) unless there is a SPECIFIC reason
- Tactus uses **LiteLLM (via DSPy)** for ALL LLM calls, which provides unified multi-provider support
- LiteLLM handles all provider-specific API calls internally
- Adding provider SDKs creates maintenance burden and can lead to bugs where code bypasses the LiteLLM layer
- Exception: `boto3` is needed for Bedrock support, but all actual LLM calls still go through LiteLLM

Example:
```lua
-- Tool definition
Tool "done" { use = "tactus.done" }

-- OpenAI agent
Agent "openai_agent" {
    provider = "openai",
    model = {
        name = "gpt-4o",
        temperature = 0.7
    },
    system_prompt = "...",
    toolsets = {"done"}
}

-- Bedrock agent
Agent "bedrock_agent" {
    provider = "bedrock",
    model = "anthropic.claude-3-5-sonnet-20240620-v1:0",
    system_prompt = "...",
    toolsets = {"done"}
}
```

## Production Readiness

**IMPORTANT**: Tactus is **NOT** ready for production. It is in early development (Alpha status).

### Do NOT:
- Declare that Tactus is "ready for production"
- Claim that features are "production-ready"
- State that the project is "complete" or "finished"
- Use phrases like "ready to use in production" or "production-ready"

### Do:
- Focus on testing and verification
- Run existing tests before declaring changes complete
- Verify that implementations actually work as intended
- Acknowledge limitations and incomplete features
- Suggest improvements and note areas that need work

## Testing Philosophy (BDD-First)

Tactus aspires to be **religiously BDD** and **spec-first**:
- **Outside-in first**: Start with BDD specs that narrate the feature behavior.
- **Specs as story**: Scenarios should read like a short narrative of how the feature works.
- **Pytest is secondary**: Use unit tests only when a behavior is best verified at the unit level.
- **Unit tests are limited**: Prefer BDD unless a unit test is the most sensible and lowest-friction way to verify correctness.

## Semantic Release and Changelog

**IMPORTANT**: This project uses Semantic Release to automatically manage versioning and the changelog.

- **Do NOT manually edit `CHANGELOG.md`**. It is generated and updated automatically by the release workflow.
- **Do NOT add `CHANGELOG.md` to `.gitignore`**. It must be tracked in the repository so the release bot can commit updates to it.
- **Do NOT delete or truncate `CHANGELOG.md`**.
- Ensure your commit messages follow the [Angular Commit Message Convention](https://github.com/angular/angular/blob/master/CONTRIBUTING.md#commit) (e.g., `feat: ...`, `fix: ...`, `docs: ...`) so that Semantic Release can correctly generate the changelog.

## Commit Message Guidelines

When writing commit messages:

- **Do NOT use code blocks** (backticks or triple backticks) in commit messages
- Use plain text with proper formatting (bullet points, indentation)
- Keep commit subject lines concise (50-72 characters)
- Use the imperative mood ("fix bug" not "fixed bug")
- Include detailed explanations in the commit body when necessary
- Follow the Angular Commit Message Convention for the subject line

## Git Branching Strategy

**Branch naming conventions** - Use these prefixes for all branches:

- `feature/` - New features or enhancements (e.g., `feature/preferences-ui`, `feature/mcp-server-config`)
- `fix/` - Bug fixes (e.g., `fix/config-cascade-merge`)
- `docs/` - Documentation changes (e.g., `docs/update-api-guide`)
- `refactor/` - Code refactoring (e.g., `refactor/config-manager`)
- `test/` - Test additions or improvements (e.g., `test/add-preferences-e2e`)

**IMPORTANT**: Always use `feature/` prefix for feature branches, NOT `feat/` or `feat-`.

**Branch workflow**:
1. Create feature branch from `main`: `git checkout -b feature/my-feature`
2. Make changes and commit following commit message guidelines
3. Push to remote: `git push -u origin feature/my-feature`
4. Create pull request to `main` branch
5. After approval and merge, delete feature branch

## Parser Generation Requirements

**IMPORTANT**: Tactus uses ANTLR4 to generate parsers from the Lua grammar for both Python and TypeScript.

### Requirements for Parser Generation

**Docker is REQUIRED** for generating parsers:
- Parser generation uses ANTLR4 which requires Java
- We use Docker to avoid requiring Java installation on developer machines
- Docker image: `eclipse-temurin:17-jre`

**When to regenerate parsers:**
- Only when modifying the Lua grammar files
- Generated parsers are committed to version control
- End users don't need Docker or Java

**How to regenerate parsers:**
```bash
# Ensure Docker is running
make generate-parsers

# Or generate individually:
make generate-python-parser
make generate-typescript-parser
```

**Generated files (committed to repo):**
- `tactus/validation/generated/*.py` - Python parser
- `tactus-ide/frontend/src/validation/generated/*.ts` - TypeScript parser

## Container Development Mode

**IMPORTANT**: The sandbox container uses development mode to avoid constant rebuilds during active development.

### What is Development Mode?

Development mode (`dev_mode: true`) mounts your live Tactus source code into the container at runtime. This means:
- Code changes are **instantly available** in containers
- No rebuilding needed after changes
- No version mismatch errors between host and container

### How It Works

The IDE automatically enables dev mode. The system finds your Tactus repository via:
1. `TACTUS_DEV_PATH` environment variable (if set)
2. Python module location (`tactus.__file__` when installed with `pip install -e .`)
3. Current working directory (if it contains `tactus/` and `pyproject.toml`)

### For Tactus Developers (Typical Workflow)

If you installed Tactus with `pip install -e .` from a repo clone:
- ✅ Dev mode works automatically everywhere
- ✅ No manual configuration needed
- ✅ No need to be in repo directory

### Initial Container Build

Build the container once initially:
```bash
docker build -t tactus-sandbox:local -f tactus/docker/Dockerfile .
```

After that, code changes are instantly available with dev mode enabled.

### When Dev Mode Activates

You'll see this log message:
```
INFO:tactus.sandbox.container_runner:[DEV MODE] Mounting live Tactus source from: /path/to/Tactus
```

If it can't find the source (e.g., PyPI-installed Tactus), you'll see:
```
WARNING:tactus.sandbox.container_runner:[DEV MODE] Could not locate Tactus source directory, using baked-in version
```

### When to Rebuild Container

Only rebuild when:
- Changing dependencies in `pyproject.toml`
- Updating base system packages in Dockerfile
- Dev mode cannot find your source (rare)

**Never rebuild for regular code changes** - that's what dev mode prevents.

### CRITICAL: Auto-Rebuild on Code Changes

**IMPORTANT**: The sandbox automatically rebuilds when it detects changes to core Tactus files. The hash includes:
- `tactus/dspy/` - DSPy integration
- `tactus/adapters/` - Adapters
- `tactus/broker/` - Broker client (used by sandbox for API calls)
- `tactus/core/` - Core runtime
- `tactus/primitives/` - Primitives
- `tactus/sandbox/` - Sandbox infrastructure
- `tactus/stdlib/` - Standard library
- `tactus/docker/` - Docker configuration
- `pyproject.toml` - Dependencies

**Common Pitfall**: When you make changes to these files (especially `tactus/broker/client.py`), the sandbox image is automatically rebuilt on the next `tactus run` command. However, AI agents often forget this and run tests with outdated containers, leading to confusing errors like:
- `TypeError: BrokerClient.llm_chat() got an unexpected keyword argument 'tools'`
- New parameters not being recognized
- Changes seemingly not taking effect

**Solution**: After making changes to any of the above paths, the next `tactus run` will automatically rebuild the sandbox image with your new code. Just wait for the rebuild to complete before declaring victory. Look for log lines indicating the build is happening.

See [docs/development-mode.md](docs/development-mode.md) for complete details.

### Docker Sandbox Defaults (CLI)

- The CLI requires Docker sandboxing by default. If Docker is unavailable, `tactus run` should error rather than silently running without isolation.
- Easy opt-out is explicit: `--no-sandbox` or `sandbox.enabled: false`.
- For PyPI installs without a local source tree, the sandbox image builds by installing the matching Tactus version from PyPI inside the container.

## Tactus IDE Development

When working on the Tactus IDE:

### Architecture: Hybrid Validation

The IDE uses a two-layer validation approach for optimal performance and user experience:

**Layer 1: TypeScript Parser (Client-Side)**
- Location: `tactus-ide/frontend/src/validation/`
- ANTLR-generated from same `LuaLexer.g4` and `LuaParser.g4` grammars as Python parser
- Purpose: Instant syntax validation (< 10ms)
- Runs in browser, no backend needed
- Provides immediate feedback as user types
- Works offline

**Layer 2: Python LSP (Backend)**
- Location: `tactus-ide/backend/`
- Uses existing `TactusValidator` from `tactus/validation/`
- Purpose: Semantic validation and intelligence
- Debounced (300ms) to reduce load
- Provides completions, hover, signature help
- Cross-reference validation

### Why Hybrid?

1. **Performance**: Syntax errors appear instantly (no network delay)
2. **Offline**: Basic editing works without backend
3. **Intelligence**: LSP adds semantic features when available
4. **Scalability**: Reduces backend load (syntax is client-side)
5. **User Experience**: No lag, no waiting for validation

### Backend (Python LSP Server)
- Location: `tactus-ide/backend/`
- Uses existing `TactusValidator` from `tactus/validation/`
- Implements LSP protocol for language intelligence
- Flask server provides HTTP and WebSocket endpoints
- Focus on semantic validation, not syntax (handled client-side)

### Frontend (React + Monaco)
- Location: `tactus-ide/frontend/`
- Monaco Editor for code editing (same as VS Code)
- TypeScript parser for instant syntax validation
- LSP client communicates with Python backend via WebSocket
- Can be packaged as Electron app

### Testing IDE Features
- TypeScript parser: `cd tactus-ide/frontend && npm test`
- Backend LSP: `pytest tactus-ide/backend/` (when tests are added)
- Integration: Test with example `.tac` files
- Verify both layers work independently and together

### Running the IDE

```bash
# Terminal 1: Backend
cd tactus-ide/backend
pip install -r requirements.txt
python app.py

# Terminal 2: Frontend
cd tactus-ide/frontend
npm install
npm run dev
```

### Electron Packaging
The IDE is designed to run as a desktop application:
- Backend runs as subprocess or separate service
- Frontend uses Electron's IPC for file operations
- No dependency on browser-specific APIs
- Hybrid validation works in Electron environment

### UI/UX Standards

When working on the Tactus IDE frontend:

- **UI Framework**: Use [Shadcn UI](https://ui.shadcn.com/) components for all UI elements
- **AI Components**: Use [AI SDK Elements](https://ai-sdk.dev/elements) components by default for AI-related UI patterns
  - Confirmation dialogs: Use the [Confirmation component](https://ai-sdk.dev/elements/components/confirmation) pattern
  - Follow AI SDK Elements patterns for conversational interfaces, prompts, and responses
- **Icons**: Always use [Lucide React](https://lucide.dev/) icons - **NEVER use emojis**
- **Styling**: Use Tailwind CSS with the existing design system
- **Theme**: Support both light and dark modes (colors are defined in CSS variables)
- **Accessibility**: Ensure proper ARIA labels and keyboard navigation

Example icon usage:
```tsx
import { Bot, CircleCheck, ChevronDown } from 'lucide-react';

<Bot className="h-5 w-5 text-muted-foreground stroke-[2]" />
```

### CLI and Logging Standards

When working on CLI output, logging, or documentation:

- **NEVER use emojis** - Always use Unicode symbols instead
- **CLI Output**: Use box-drawing characters (│ ─ ├ └), arrows (→ ←), bullets (•), checkmarks (✓ ✗)
- **Logging**: Use plain text or Unicode symbols for status indicators
- **Documentation**: Use Unicode symbols or standard markdown formatting

Example symbols:
```python
# Good - Unicode symbols
print("✓ Test passed")
print("✗ Test failed")
print("→ Processing...")
print("• Item 1")

# Bad - Emojis
print("✅ Test passed")  # ❌ Don't use
print("🔥 Error")       # ❌ Don't use
```

## Testing Requirements

Before declaring any change complete:

1. **Run existing tests**: Use `pytest` to verify no regressions
2. **Test the specific feature**: Create or update tests for new functionality
3. **Verify imports**: Ensure all imports resolve correctly
4. **Check for errors**: Run linters and fix any issues
5. **Test parser changes**: If grammar modified, run `make test-parsers`

### Understanding Testing vs. Evaluation

Tactus has two distinct testing mechanisms that serve different purposes:

**Behavior Specifications (`specifications`):**
- Test the **Lua orchestration logic** (control flow, state management, coordination)
- Use Gherkin syntax (Given/When/Then)
- Run with `tactus test`
- Can use mocks to isolate logic from LLM behavior
- Fast and deterministic
- Example: Testing that a multi-agent workflow delegates correctly

**Evaluations (`evaluations`):**
- Test the **LLM's output quality** (accuracy, consistency, helpfulness)
- Use Pydantic AI Evals framework
- Run with `tactus eval`
- Use real API calls (not mocked)
- Slower and probabilistic
- Example: Testing that an agent generates high-quality greetings

**When to use which:**
- **Complex orchestration** → Use `specifications` to test the logic
- **Simple LLM wrapper** → Use `evaluations` to test the output
- **Both** → Use specifications for fast feedback on logic, evaluations for quality metrics

**Key principle:** Don't mock LLMs in evaluations—you're testing the model's actual behavior. Do mock them in specifications when you're testing orchestration logic, not intelligence.

## Strict Behavior-Driven Development Policy

- **Specifications first**: every new behavior begins with a failing `features/*.feature` scenario before implementation starts.
- **Single vocabulary**: use the established domain terms consistently in specs so the language stays stable over time.
- **No “just tests”**: behavior specifications are architecture; they define what the system *is* rather than merely verifying it.
- **Specification completeness**: every surface behavior must have a specification. If a behavior cannot be expressed cleanly, it should be removed or treated as a hard error.
- **100% coverage mandate**: every line of code must be exercised by BDD scenarios. Partial coverage is unacceptable.

## Working Backwards (Product-First Workflow)

- Draft a PR-FAQ for every new feature before coding so the product intent is explicit and the scope is understood.
- Once the PR-FAQ is approved, author the README/Sphinx docs as if the feature already exists—this drives implementation clarity and discoverability.
- Write BDD specifications that mirror and reinforce the documentation, then implement to match those scenarios exactly.
- Finish with rigorous quality gates: documentation, clear naming, validation, and the 100% coverage requirement.

## Documentation as a Runnable Textbook

- Treat documentation as narrative teaching material: explanations must be paired with runnable examples using the ships-included demo data.
- Prefer elementary, educational examples that build progressively toward advanced techniques.
- Every documented concept needs an executable walkthrough so users can learn by doing.
- Keep docs tightly aligned with actual commands, scripts, and outputs.

## One Official Way

- No backwards compatibility baggage or dual APIs—there is a single authoritative approach for each domain concept.
- Avoid hidden fallbacks; prefer explicit errors that surface misconfiguration or invalid states.
- Use the shared domain vocabulary across code, documentation, and specifications to keep the model clean and durable.

## Pydantic-First Domain Modeling

- Represent domain constructs that cross boundaries (configs, APIs, tool schemas, CLI output) with Pydantic models.
- Surface validation errors as user-friendly messages, especially in the CLI and tool contexts.

## Code Quality

- **No line-level comments** unless capturing a high-level idea that cannot be conveyed through naming; avoid running commentary.
- Use Sphinx-style docstrings with reStructuredText field lists (`:param`, `:type`, `:return`, `:rtype`, `:raises`, `:ivar`, `:vartype`) on public APIs.
- Keep implementations small, readable, and consistent with existing patterns; add logging judiciously to aid debugging.
- Emphasize intent through specs, docstrings, validation, and typing rather than through implementation noise.
- Black and Ruff compliance is mandatory; documentation tooling must support docstring generation.
- **Readability-first mandate**: prioritize clarity over brevity. Prefer long, descriptive names and explicit structure so code reads like precise pseudocode.
- **Expert judgment encouraged**: use your best professional knowledge about readability (Python best practices and general software design) to improve clarity, even when it requires structural refactors that preserve behavior.
- **Over-clarity bias**: if there is a tradeoff, choose the option that improves explicitness, transparency, and maintainability, especially at the cost of extra lines or more verbose naming.

### Code Quality Optimization Loop (Required)

Repeat this loop for each iteration of readability improvements:

1. Identify readability improvements (prioritize high-impact or high-traffic code paths).
2. Make the largest safe readability refactor you can without changing behavior.
3. Run the explicit test commands first (match the Pre-Commit Checklist flags):
   - `pytest tests/ -x -k "not test_real_execution"`
   - `behave --summary`
4. Run the full local quality gate **including Ruff and Black** (do not skip):
   - `ruff check .`
   - `black tactus tactus-ide/backend features/steps tests`
   - `black tactus tactus-ide/backend features/steps tests --check`
5. Run the full coverage suite and regenerate reports:
   - `scripts/run_coverage.sh`
6. If anything fails, fix immediately, then repeat steps 3–5 before continuing.

## Using the CLI for Development

The Tactus CLI provides powerful tools for developing and debugging agents.

### Formatting `.tac` Files

Use `tactus format` to automatically reindent and normalize whitespace in `.tac` files.

### Running and Debugging Procedures

When you run a procedure with `tactus run`, you get real-time visibility into what's happening:

```bash
tactus run examples/04-basics-simple-agent.tac
```

Output shows:
- **Agent activity**: See when agents start processing and complete
- **Tool calls**: See what tools agents call with full arguments and results
- **Agent responses**: See the actual text/reasoning from the LLM
- **Cost tracking**: Monitor tokens and costs for each LLM call
- **Summary**: Final iteration count, tools used, total cost

Example output:
```
Running procedure: 04-basics-simple-agent.tac (lua format)

→ Agent greeter: Waiting for response...
Hello! I'll help you with that task.
✓ Agent greeter: Completed 1204ms
→ Tool done
  Args: {
  "reason": "Hello there! I hope you're having a wonderful day."
}
  Result: Done
$ Cost greeter: $0.001267 (354 tokens, openai:gpt-4o, 1204ms)

✓ Procedure completed: 1 iterations, 1 tools used

$ Cost Summary
  Total Cost: $0.001267
  Total Tokens: 354
```

### Inspecting Procedure Structure

Use `tactus info` to view procedure metadata without running it:

```bash
tactus info examples/04-basics-simple-agent.tac
```

This shows:
- **Parameters**: What inputs the procedure expects
- **Outputs**: What results it returns
- **Agents**: Configuration for each agent (provider, model, tools, prompt preview)
- **Specifications**: Count of BDD test scenarios

This is useful for:
- Understanding what a procedure does before running it
- Checking agent configurations
- Verifying tool availability
- Documentation and code review

### Debugging Agent Issues

If an agent doesn't work as expected, the CLI output helps you diagnose:

1. **Agent never calls done tool**: Look for tool call events (→ Tool). If you don't see any, check:
   - Does the agent definition include `tools = {"done"}`?
   - Does the system prompt mention calling the done tool?

2. **Agent calls wrong tool**: Tool call events show arguments. Check:
   - Are tool names correct in the agent config?
   - Does the system prompt clearly explain which tools to use?

3. **High costs/token usage**: Cost events show per-call breakdown. Look for:
   - Agents making too many turns (increase max_turns or improve prompts)
   - Large context windows (check message history filtering)
   - Repeated tool calls (agent might be stuck in a loop)

4. **Slow execution**: Timing information shows where delays occur:
   - Agent turns show duration (e.g., "1204ms")
   - Multiple slow turns indicate LLM performance issues
   - Consider using faster models for simple tasks

### CLI Output Format

The CLI uses Unicode symbols (not emojis) for compatibility:

- `→` Agent or tool activity starting
- `✓` Successful completion
- `✗` Error or failure
- `$` Cost information
- `•` List items

All output is plain text with optional ANSI colors for readability in terminals.

## Project Status

Tactus is a standalone workflow engine extracted from a larger project. It is:
- In active development
- Missing some features (noted in code with TODO comments)
- Subject to API changes
- Not yet suitable for production use

When working on Tactus, focus on:
- Making incremental improvements
- Fixing bugs and issues
- Adding missing functionality
- Improving documentation
- Writing and maintaining tests
