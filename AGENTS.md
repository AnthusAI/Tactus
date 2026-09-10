## Project management with Kanbus

Use Kanbus for task management.
Why: Kanbus task management is MANDATORY here; every task must live in Kanbus.
When: Create/update the Kanbus task before coding; close it only after the change lands.
How: See CONTRIBUTING_AGENT.md for the Kanbus workflow, hierarchy, status rules, priorities, command examples, and the mistakes to avoid. Never inspect project/ or issue JSON directly (including with cat or jq); use Kanbus commands only.
Performance: Prefer kbs (Rust) when available; kanbus (Python) is equivalent but slower.
Warning: Editing project/ directly violates The Way. Do not read or write anything in project/; work only through Kanbus.
Git / PR policy: Rules for product-code commits, branch names, pull requests, and human approval live in this repository's AGENTS.md (outside this Kanbus section). CONTRIBUTING_AGENT.md covers Kanbus board mechanics such as `kbs commit`; follow AGENTS.md for product code and git workflow.
Artifact sync rule: If Kanbus operations create or update files under `project/issues/` or `project/events/`, stage and commit those artifact files in the same branch before opening a PR. Shared `kbs commit` persists `project/issues/` only; commit `project/events/` manually when your branch changes event logs.

## SOP compliance

** When completing an epic/milestone/task/feature/fix, you MUST complete ALL steps below. Work is NOT complete until `git push` succeeds AND the CI passes in GitHub, which you need to check with `gh`.  Set a timer and wait for it to finish, and if it's not done yet then wait longer.  Iterate on fixing the problem until CI passes in GitHub Actions.

## Git Flow policy (mandatory)

- This repository uses git-flow. Do not commit directly to `develop` or `main`.
- Start every change on a dedicated branch from `develop` (for example `feature/...`, `bugfix/...`, or `chore/...`).
- Commit and push only to that branch, then open a PR into `develop` only when all related Kanbus tasks are `done`/`closed` and the user confirms to open a PR (or explicitly requests a PR).
- Only merge to `main` via PR from `develop` after required checks pass.
- If you accidentally commit to `develop` or `main`, stop and ask before applying any history rewrite or revert strategy.

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

## Repo layout

- `tactus/` — Python package (runtime, CLI, stdlib, validation)
- `tests/` — Python tests (unit + integration markers)
- `features/` — Behave BDD feature files
- `examples/` — runnable `.tac` programs (many have BDD specs)
- `docs/` — canonical documentation for the language and primitives
- `tactus-ide/` — web IDE (Flask backend + React frontend)
- `tactus-lsp-server/` — Language Server Protocol server
- `tactus-vscode/` — VS Code extension
- `tactus-desktop/` — Electron desktop app

## Quality gates

Run these before pushing when code has changed:

```bash
ruff check .
black --check .
./test-ci.sh                          # unit tests (same as CI)
behave --tags=-skip                   # BDD integration tests
```

Focused targets:

```bash
pytest tests/cli -q                   # just CLI tests
make test-examples-fast               # examples without slow/integration
make test-examples-bdd                # only examples with BDD specs
```

## LLM Debug Mode

Set `PLEXUS_DEBUG_LLM=1` to log the full input and output of every LLM call made by a Tactus agent. This is implemented in `tactus/dspy/agent.py` in the `_log_llm_debug_input` and `_log_llm_debug_output` methods, called from both `_turn_without_streaming` and `_turn_with_streaming`.

The debug output includes: system prompt, conversation history (with role labels), user message, available tools, model response text, and tool calls. All output goes to the Python logger (stderr via Rich).

## CI debugging

Use `gh` (never scrape with curl):

```bash
gh run list --limit 10
gh run view <run_id>
gh run view <run_id> --log-failed
```

When CI is red: read the failing job logs, reproduce locally, fix, push, re-check.

## Cursor Cloud specific instructions

### Development setup

Dependencies are installed by the VM update script (`python3 -m poetry install --extras "dev"` and `pip install -e tactus-lsp-server/`). The `tactus` CLI is installed into `~/.local/bin`; ensure `PATH` includes it (the update script handles this).

### Running the CLI

- Use `--no-sandbox` when Docker is unavailable: `tactus run <file>.tac --no-sandbox`
- `tactus run` / `tactus test` / `tactus eval` against agent-based `.tac` files require `OPENAI_API_KEY` (or Bedrock credentials).
- Pure-logic `.tac` files (e.g. `examples/02-basics-simple-logic.tac`) can run and be tested without any API key.

### Gotchas

- `python` is not on PATH in the Cloud VM; always use `python3`.
- `~/.local/bin` must be on PATH. Add `export PATH="$HOME/.local/bin:$PATH"` if missing.
- Do not run `npm run dev` or type checking (takes too long).
- Do not run `tactus run` on agent-based examples without `OPENAI_API_KEY`.
