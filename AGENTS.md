# Instructions for Coding Agents

This document provides guidelines for AI coding agents working on the Tactus project.

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

Example:
```yaml
agents:
  openai_agent:
    provider: openai
    model:
      name: gpt-4o
      temperature: 0.7
    system_prompt: "..."
    tools: [done]
  
  bedrock_agent:
    provider: bedrock
    model: anthropic.claude-3-5-sonnet-20240620-v1:0
    system_prompt: "..."
    tools: [done]
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

## Semantic Release and Changelog

**IMPORTANT**: This project uses Semantic Release to automatically manage versioning and the changelog.

- **Do NOT manually edit `CHANGELOG.md`**. It is generated and updated automatically by the release workflow.
- **Do NOT add `CHANGELOG.md` to `.gitignore`**. It must be tracked in the repository so the release bot can commit updates to it.
- **Do NOT delete or truncate `CHANGELOG.md`**.
- Ensure your commit messages follow the [Angular Commit Message Convention](https://github.com/angular/angular/blob/master/CONTRIBUTING.md#commit) (e.g., `feat: ...`, `fix: ...`, `docs: ...`) so that Semantic Release can correctly generate the changelog.

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

## Tactus IDE Development

When working on the Tactus IDE:

### Architecture: Hybrid Validation

The IDE uses a two-layer validation approach for optimal performance and user experience:

**Layer 1: TypeScript Parser (Client-Side)**
- Location: `tactus-ide/frontend/src/validation/`
- ANTLR-generated from same `Lua.g4` grammar as Python parser
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
- **Icons**: Always use [Lucide React](https://lucide.dev/) icons - **NEVER use emojis**
- **Styling**: Use Tailwind CSS with the existing design system
- **Theme**: Support both light and dark modes (colors are defined in CSS variables)
- **Accessibility**: Ensure proper ARIA labels and keyboard navigation

Example icon usage:
```tsx
import { Bot, CircleCheck, ChevronDown } from 'lucide-react';

<Bot className="h-5 w-5 text-muted-foreground stroke-[2]" />
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

## Code Quality

- Follow existing code patterns and style
- Add appropriate logging for debugging
- Include docstrings for public APIs
- Handle errors gracefully with proper exception types
- Keep implementations simple and maintainable

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
