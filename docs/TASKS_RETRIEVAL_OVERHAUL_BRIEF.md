# Tasks + Retrieval UX Overhaul (Contractor Handoff)

## Purpose
Define and implement the new Tactus + Biblicus retrieval UX with:
- Tasks as first-class, statically discoverable entrypoints
- Corpus extraction handled automatically on ingest
- Retriever tasks (index/clean/etc.) exposed automatically
- Consistent, simplified vocabulary

This brief is the source of truth for implementation decisions.

## Goals
- High-level, readable Tactus code with minimal cognitive overhead.
- Static task discovery (parse tree only, no execution).
- Corpus is retriever-agnostic; retrievers are pluggable.
- Automatic extraction on ingest when a corpus pipeline is configured.
- Automatic retriever task exposure (index/clean/etc.) based on retriever type.
- Maintain existing Procedure + script-mode behavior (Tasks augment, not replace).

## Non-Goals
- Backward compatibility for old naming or legacy DSL conventions.
- Running any Lua code to discover tasks.
- Introducing new language primitives for pipelines (pipeline is configuration).

## Canonical Vocabulary (New)
- Task
- Corpus
- Retriever
- Snapshot
- Evidence
- Configuration
- Pipeline
- Load
- Ingest
- Extract
- Index
- Query

Removed from user-facing vocabulary:
- backend
- recipe
- run (for retrieval artifacts)

Internal-only (Biblicus):
- catalog

## DSL Shape (New)

### Corpus
```lua
local FilesystemCorpus = require("tactus.corpora.filesystem")

miami_afd = FilesystemCorpus.Corpus {
  root = "tests/fixtures/noaa_afd_corpus/MFL",
  configuration = {
    pipeline = {
      extract = ExtractionPipeline {
        -- composed extraction steps
      }
    }
  }
}
```

### Retriever
```lua
local TfVector = require("tactus.retrievers.tf_vector")

miami_search = TfVector.Retriever {
  corpus = miami_afd,
  configuration = {
    pipeline = {
      query = {
        limit = 3,
        maximum_total_characters = 20000
      }
    }
  }
}
```

### Task (explicit)
```lua
Task "fetch" {
  provides = { kind = "load", corpus = "miami_afd" },
  Task "NOAA" {
    entry = function()
      return FetchNoaaAfd { wfo = "MFL", max_items = 5, corpus = miami_afd }
    end
  }
}
```

### Task (assignment sugar)
```lua
fetch = Task {
  provides = { kind = "load", corpus = "miami_afd" },
  NOAA = Task {
    entry = function()
      return FetchNoaaAfd { wfo = "MFL", max_items = 5, corpus = miami_afd }
    end
  }
}
```

Task entry values should be functions to avoid evaluation at declaration time:
```lua
run = Task {
  entry = function()
    return Miami("Summarize the recent Miami AFD.")
  end
}
```
Script-mode returns remain valid for simple workflows (no Task required).

Rules for assignment sugar:
- If the Task has no string name, the LHS identifier becomes the task name.
- If both LHS name and string name exist, they must match or error.
- Names are scope-local; duplicates at the same scope are hard errors.
- Task names may not contain ':' (reserved for subcommand notation).

## Task Includes Across Files
Tasks may be defined in separate files and included into a main file.

### Required syntax
```lua
IncludeTasks("tasks/noaa_fetch.tac")
```

### Optional namespace
```lua
IncludeTasks("tasks/noaa_fetch.tac", "fetch")
```
This makes all tasks in the included file available as `fetch:<task>`.

### Static discovery rules
- Include paths must be string literals (no variables/expressions).
- Includes are parse-only (no execution, no require side effects).
- Includes can be nested; cycles are hard errors.
- Task ordering follows the include position in the main file.
- Included files must contain only Task declarations (no executable code).

### Scope
Included tasks share the main file scope so they can reference corpora/retrievers
that are defined in the main file.

## Entrypoint Resolution (Augments Existing Behavior)
Priority order:
1) Explicit task invocation wins.
2) `tactus file.tac run`:
   - runs `run` task if present
   - otherwise falls back to the main Procedure/script-mode entrypoint
3) `tactus file.tac` default:
   - if exactly one task exists, run it
   - else if `run` task exists, run it
   - else run main Procedure/script-mode if present
   - otherwise list tasks and exit

This preserves existing Procedure/script-mode behavior exactly.

## Script Mode Compatibility
The script-mode transform must treat these as declarations (not executable code):
- Task
- Corpus
- Retriever
- Context
- IncludeTasks

## Automatic Extraction
- If `Corpus.configuration.pipeline.extract` exists, extraction runs automatically on ingest.
- No explicit extraction task is required unless overriding the default behavior.

## Automatic Retriever Tasks
- Retriever types declare supported tasks via static metadata (no DSL expose syntax).
- The CLI aggregates those into commands:
  - `tactus file.tac index` runs all retrievers that support index, in declaration order.
  - `tactus file.tac index:retriever_name` runs only that retriever.
- If a user-defined `Task "index"` exists, it overrides auto-aggregation.

## Biblicus-First Task Dependencies (Load → Extract → Index)
- Biblicus owns dependency planning/execution via `Task` + `Plan` (no TaskSpec).
- Built-in dependency rules:
  - `query → index` (if no compatible retrieval snapshot exists)
  - `index → extract` (always)
  - `extract → load` (only if corpus empty and a load handler exists)
  - `ingest` has no dependencies
- Default extraction pipeline is pass-through text if none configured.
- Task kind aliases normalize to canonical kinds:
  - `fetch`/`sync → load`
  - `build → index`
  - `run → query`

### Task dependency hooks (Tactus)
Tasks can plug into Biblicus dependency planning via:
- `depends_on = {"load", "extract"}`
- `provides = { kind = "load", corpus = "miami_afd" }`

`provides` lets custom tasks satisfy built-in dependency kinds.

## Snapshot Semantics
- Retrieval build artifacts are called **snapshots** (not runs/indexes).
- Use `snapshot`, `snapshot_id`, `snapshot_manifest`, `snapshot_artifacts`.
- Extraction artifacts are also snapshots (extraction snapshot).

## Acceptance Criteria (Must Pass)

Task discovery:
- Task list derived from parse tree only (no execution).
- `fetch = Task { NOAA = Task { ... } }` produces `fetch` and `fetch:NOAA`.
- `foo = Task "bar" { ... }` errors if names differ.

Entrypoint behavior:
- Script mode still runs exactly as today.
- `tactus file.tac run` falls back to main procedure if no run task exists.
- `tactus file.tac` follows default rules above.

Retriever auto-tasks:
- If two retrievers support `index`, `tactus file.tac index` runs both in order.
- `tactus file.tac index:retriever_a` runs only that retriever.
- User-defined `Task "index"` overrides auto aggregation.

Dependency planning:
- `tactus file.tac run` prompts when dependencies (load/extract/index) are required.
- `tactus file.tac run --auto-deps` executes dependency tasks without prompting.
- `tactus file.tac run --no-deps` fails fast if dependencies are missing.
- `provides` tasks can satisfy `load` dependencies (e.g. fetch task).

Extraction:
- `pipeline.extract` runs automatically on ingest.
- No explicit extraction task required.

Snapshot terminology:
- Docs/CLI/API use snapshot, not run/index.

## Implementation Plan (Steps)
1) Vocabulary + DSL spec doc (this file is the source of truth).
2) Parser/semantic visitor updates (Task, IncludeTasks, sugar, nested tasks).
3) Task registry builder (static parse only, include resolution).
4) Entrypoint resolution wiring (Tasks + existing Procedure/script mode).
5) Retriever auto-task exposure (static metadata + CLI aggregation).
6) Corpus ingest -> automatic extraction (if pipeline.extract exists).
7) Rename terminology to snapshot/configuration/retriever in docs/CLI/API.
8) Update examples + BDD specs.

## Mapping Table (Old -> New)
Biblicus and Tactus terminology:
- backend -> retriever
- backend id -> retriever id / retriever type
- recipe -> configuration
- build run / retrieval run -> snapshot
- run id -> snapshot id
- run manifest -> snapshot manifest
- backend index artifacts -> snapshot artifacts
- query run -> query snapshot (or query with snapshot ref)

## Example (New Way)
```lua
-- NOAA AFD retrieval example
local FilesystemCorpus = require("tactus.corpora.filesystem")
local TfVector = require("tactus.retrievers.tf_vector")

miami_afd = FilesystemCorpus.Corpus {
  root = "tests/fixtures/noaa_afd_corpus/MFL",
  configuration = {
    pipeline = {
      extract = ExtractionPipeline {
        -- composed extraction steps
      }
    }
  }
}

miami_search = TfVector.Retriever {
  corpus = miami_afd,
  configuration = {
    pipeline = {
      query = {
        limit = 3,
        maximum_total_characters = 20000,
        include_metadata = true,
        metadata_fields = { "published" }
      }
    }
  }
}

fetch = Task {
  NOAA = Task {
    entry = function()
      return FetchNoaaAfd { wfo = "MFL", max_items = 5, corpus = miami_afd }
    end
  }
}

-- Script-mode entrypoint remains valid for simple workflows:
return Miami("Summarize the recent Miami AFD.")
```
