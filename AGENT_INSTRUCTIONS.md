# Detailed Agent Instructions for Tactus Development

For project overview and the required end-of-session checklist, see `AGENTS.md`.

This document is the operational runbook for making changes in this repository (Tactus),
including Beads workflow, quality gates, and CI debugging.

## Repo Shape (high level)

- `tactus/`: the Python package (runtime, CLI, stdlib, validation)
- `tests/`: Python tests (unit + integration markers)
- `examples/`: runnable `.tac` programs (many have BDD specs)
- `docs/`: canonical documentation for the language + primitives
- `tactus-desktop/`, `tactus-ide/`, `tactus-web/`: related desktop/IDE/web code

## Beads (required)

This repo uses Beads for task tracking via the `bd` CLI.

- Create issues for follow-ups: `bd create "Title" -p 2 -t task --description "..."`.
- Avoid interactive editors: do not use `bd edit` (agents cannot use `$EDITOR`).
- Update with flags: `bd update <id> --title ... --description ... --acceptance ...`.
- Close when done: `bd close <id> --reason "..."`.
- Sync often: `bd sync` (exports `.beads/issues.jsonl`, commits, pulls, imports, pushes).

Commit messages should include the bead ID in parentheses, e.g.:

```bash
git commit -m "Fix registry tags for trained models (Tactus-abc)"
```

## Local Setup (typical)

```bash
python -m venv .venv
./.venv/bin/pip install -e ".[dev]"
```

Optional ML extras (install only when needed):

```bash
./.venv/bin/pip install -e ".[ml]"   # scikit-learn + datasets + joblib
./.venv/bin/pip install -e ".[hf]"   # transformers + torch + datasets
```

## Quality Gates (run these when code changes)

CI runs a Python-version matrix and enforces formatting/linting. Before pushing:

```bash
./test-ci.sh                 # closest to CI test invocation
./.venv/bin/ruff check .
./.venv/bin/black --check .
```

Common focused targets:

```bash
pytest tests/cli -q
make test-examples-fast
make test-examples-bdd
```

If you touched the grammar / parser generation:

```bash
make generate-parsers
make test-parsers
```

## CI Debugging (GitHub Actions)

Use the `gh` CLI (do not scrape with curl).

```bash
gh run list --limit 10
gh run view <run_id>
gh run view <run_id> --log-failed
gh run view <run_id> --job <job_id> --log
```

When CI is red:

1) Open the latest failed run and read the failing job logs.
2) Reproduce locally using the closest command (`./test-ci.sh`, `black --check`, etc.).
3) Fix, commit, push, and re-check `gh run list` until the latest run is green.

## Landing The Plane (mandatory)

When ending a work session, you must push successfully. Follow `AGENTS.md` exactly:

```bash
git pull --rebase
bd sync
git push
git status  # must show up to date with origin/main
```

## Optional: Beads Git Hooks

If you use Beads heavily across multiple machines/workspaces, install the hooks once:

```bash
bd hooks install
```

This helps keep `.beads/issues.jsonl` consistent (flush on commit/push; import on pull/checkout).
