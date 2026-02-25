## Git Flow

This project uses **Git Flow**. The `dev` branch is the integration branch for all feature work. **Never push directly to `main`.**

- **Feature branches** branch from `dev` and merge back into `dev`.
- **Release branches** branch from `dev` and merge into both `main` and `dev`.
- **Hotfix branches** branch from `main` and merge into both `main` and `dev`.

When Cursor Cloud assigns you a feature branch (e.g. `cursor/some-task-xxxx`), it should be based on `dev`, not `main`.

## Project management with Kanbus

Use Kanbus for task management.
Why: Kanbus task management is MANDATORY here; every task must live in Kanbus.
When: Create/update the Kanbus task before coding; close it only after the change lands.
How: See CONTRIBUTING_AGENT.md for the Kanbus workflow, hierarchy, status rules, priorities, command examples, and the sins to avoid. Never inspect project/ or issue JSON directly (including with cat or jq); use Kanbus commands only.
Performance: Prefer kanbusr (Rust) when available; kanbus (Python) is equivalent but slower.
Warning: Editing project/ directly is a sin against The Way. Do not read or write anything in project/; work only through Kanbus.

## Landing the Plane (Session Completion)

**When ending a work session**, you MUST complete ALL steps below. Work is NOT complete until `git push` succeeds.

**MANDATORY WORKFLOW:**

1. **File issues for remaining work** - Create issues for anything that needs follow-up
2. **Run quality gates** (if code changed) - Tests, linters, builds
3. **Update issue status** - Close finished work, update in-progress items
4. **PUSH TO REMOTE** - This is MANDATORY:
   ```bash
   git pull --rebase
   git push
   git status  # MUST show "up to date with origin"
   ```
5. **Clean up** - Clear stashes, prune remote branches
6. **Verify** - All changes committed AND pushed
7. **Hand off** - Provide context for next session

**CRITICAL RULES:**
- Work is NOT complete until `git push` succeeds
- NEVER stop before pushing - that leaves work stranded locally
- NEVER say "ready to push when you are" - YOU must push
- If push fails, resolve and retry until it succeeds

## Cursor Cloud specific instructions

### Services overview

**Tactus core** is the primary product — a Python library + CLI for Lua-based agentic workflows. The monorepo also contains `tactus-lsp-server`, `tactus-ide`, `tactus-vscode`, and `tactus-desktop`, but day-to-day development centres on the core Python package.

### Development setup

Dependencies are installed by the VM update script (`pip install -e ".[dev]"` and `pip install -e tactus-lsp-server/`). The `tactus` CLI is installed into `~/.local/bin`; ensure `PATH` includes it (the update script handles this).

### Running quality gates

- **Lint:** `ruff check` (zero-config, uses settings in `pyproject.toml`)
- **Unit tests:** `pytest tests/ -v --tb=short -m "not integration" -n0` (same as `test-ci.sh`; fetch test data first with `python3 scripts/fetch_wikitext2.py`)
- **BDD integration tests:** `behave --summary` (runs 450+ scenarios, no API key needed)
- **Validate `.tac` files:** `tactus validate <file>.tac`
- **Format check:** `tactus format <file>.tac --check`

### Running the CLI

- Use `--no-sandbox` when Docker is unavailable: `tactus run <file>.tac --no-sandbox`
- `tactus run` / `tactus test` / `tactus eval` against agent-based `.tac` files require `OPENAI_API_KEY` (or Bedrock credentials).
- Pure-logic `.tac` files (e.g. `examples/02-basics-simple-logic.tac`) can run and be tested without any API key.

### Gotchas

- `python` is not on PATH in the Cloud VM; always use `python3`.
- `~/.local/bin` (where `pip install --user` places scripts like `tactus`, `ruff`, `behave`) must be on PATH. Add `export PATH="$HOME/.local/bin:$PATH"` if missing.
- The user rule says **do not run `npm run dev`** and **do not run type checking** (takes too long).
- Do not attempt to run `tactus run` on agent-based examples without setting `OPENAI_API_KEY` first.
