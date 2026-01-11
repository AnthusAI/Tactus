# Brokered Capabilities & Tool Runners (Planning)

Status: Phase 1A complete • Phase 1B (Host Tools) in progress • Phase 2 spike complete (as of Jan 2026)

This document proposes an architecture that:

- Runs the full Tactus runtime inside a sandbox container (Docker)
- Keeps long-lived secrets (API keys, credentials) out of that container entirely
- Supports **MCP stdio tools** via three execution modes (“tool runners”)
- Preserves **streaming** end-to-end (LLM streaming and UI streaming)
- Keeps the user workflow simple: tools are auto-discovered by convention

## Current Direction (Jan 2026)

We are prioritizing a **local Docker MVP** that delivers the core security invariant:

- The **runtime container is networkless** (`--network none`) and **secretless** (no keys in env, mounts, or request payloads).
- A **host-side broker** performs all privileged operations (initially: **OpenAI LLM calls**) and relays **streaming events** back to the UI.

To get to a working milestone quickly, we are explicitly deferring:

- Tool auto-discovery conventions (`tools/`, `tools-isolated/`, `tools-host/`)
- Tool package manifests (e.g., `mcp.json`)
- An explicit secret store / secrets manager integration
- `isolated` tool runner containers
- Multi-provider LLM support beyond the first proof-of-concept provider

### Current Status Snapshot

What works today:

- **Local Docker MVP (Phase 1A)**: runtime container uses **brokered LLM calls + event streaming over stdio** with `--network none`.
- **Host tools (Phase 1B, WIP)**: runtime container can call a tiny allowlisted set of **brokered host tools** via `Host.call(...)` / `tool.call` (stdio or TCP broker transport).
- **Remote-mode spike (Phase 2)**: runtime container can connect to broker via **TCP** (and optional TLS) for cloud/K8s-style deployments where Docker stdio attach doesn’t apply.

What is still deferred (intentional):

- A full tool runner system (`isolated` tool runner containers, discovery, packaging)
- Tool discovery and manifests (`tools/`, `mcp.json`, etc.)
- Secret store integration (broker still reads credentials from host environment)
- Multi-provider beyond the initial proof-of-concept path

Manual validation commands:

- Rebuild sandbox image (required after sandbox entrypoint changes): `tactus sandbox rebuild --force`
- Dev-only Docker integration smoke tests (skipped by default): `TACTUS_RUN_DOCKER_TESTS=1 pytest -m docker -v` (or `make test-docker-sandbox`)
- Networkless runtime, stdio broker transport: `tactus run examples/53-tsv-file-io.tac --sandbox --verbose`
- Brokered LLM + streaming, still networkless runtime: `tactus run examples/06-basics-streaming.tac --sandbox --verbose`
- Brokered host tools, still networkless runtime: `tactus run examples/66-host-tools-via-broker.tac --sandbox --verbose`
- Remote-mode spike over TCP (runtime network enabled): `tactus run examples/53-tsv-file-io.tac --sandbox --sandbox-broker tcp --verbose`
- Remote-mode spike LLM + streaming over TCP (runtime network enabled): `tactus run examples/06-basics-streaming.tac --sandbox --sandbox-broker tcp --verbose`

Security note: TCP mode exists to prove cloud viability. In real deployments you must enforce “runtime can only talk to broker” with infra controls (K8s NetworkPolicy / SGs), because the runtime container has network access in this mode.

## Goals

1. **Secrets never enter the untrusted container**
   - No secrets in container env
   - No secrets in mounted config files
   - No secrets in container filesystem layers
   - Default to **no outbound network** from the runtime container (LLM/tool network goes via brokered capabilities instead)
2. **Support three tool runners**
   - `sandbox`: run tool code inside the runtime container (no secrets)
   - `isolated`: run tool code in a separate tool container (secrets allowed)
   - `host`: run tool code on the host (secrets allowed, explicitly trusted)
3. **First-class streaming**
   - LLM responses stream to the runtime
   - Runtime streams to the IDE/UI (already required)
4. **Minimal “mental model” for users**
   - Everything is “tools”
   - Users mostly just drop tool folders into conventional directories
5. **Portable execution backends**
   - Same broker protocol and streaming semantics for local Docker and orchestrated workers (ECS/Fargate/EKS)
   - Isolation policy (per-run vs pooled vs shared worker) is a deployment choice, not an API change

## Non-Goals (for this design doc)

- Fully solving data exfiltration if the user gives an agent unrestricted outbound channels (that requires higher-level policy).
- Making arbitrary untrusted third-party tool code safe to run with credentials. If a process has a credential, assume it can leak/misuse it.

## Threat Model (for this design doc)

This plan assumes:

- `.tac` code is untrusted (prompt-injected, AI-generated, user-contributed).
- Tools installed into the `sandbox` runner are also untrusted.
- The developer/operator controls the broker and host configuration (secrets, which tools are allowed, and where they run).
- We aim to prevent the most common “LLM agent” failure mode: **reading or leaking host secrets via file access or environment access**.

## Terminology

- **Runtime container**: the Docker container running the Python runtime + Lua sandbox for `.tac` code.
- **Broker**: a trusted host-side process that holds secrets and performs privileged operations on behalf of the runtime container.
- **Tool runner**: where a tool server runs (`sandbox`, `isolated`, `host`).
- **Tool package**: a folder containing a tool server and a small manifest describing how to run it.
- **Workspace**: the procedure’s working directory mounted into containers at a canonical path.

## High-Level Architecture

Core idea: the runtime container is **secretless**. It talks to a **host broker** over a narrow RPC channel. The broker performs:

- LLM API calls (streaming)
- Tool execution for tools that run outside the runtime container
- Model invocations (e.g., SageMaker/Bedrock/etc) where credentials must not enter the runtime container

```
                 (no secrets)                              (has secrets)
┌───────────────────────────────┐        stdio RPC        ┌──────────────────────┐
│ Runtime container             │ <──────────────────────> │ Broker (host)         │
│ - Tactus runtime (Python)     │                         │ - LLM calls (keys)    │
│ - Lua sandbox                 │                         │ - Tool calls          │
│ - sandbox tools (/tools)      │                         │ - Model invocations   │
│ - ideally no outbound network │                         │ - launches tool procs │
└───────────────────────────────┘                         └─────────┬────────────┘
                                                                     │
                                                                     │ docker run (stdio attach)
                                                                     v
                                                          ┌──────────────────────┐
                                                          │ Tool container(s)     │
                                                          │ - MCP stdio servers   │
                                                          │ - workspace mounted   │
                                                          │ - secrets allowed     │
                                                          └──────────────────────┘
```

## Secrets & Configuration (Host-Only)

Principle: **tool packages and workspaces should be copyable; secrets should not be.**

- Tool packages must be **secret-free** (no `.env`, no embedded tokens, no per-tool `config.yml` with keys).
- Long-lived secrets live only in a host-side secret store read by the broker (env vars in the host broker process, OS keychain, `~/.tactus/secrets.yml`, etc.).
- Project/workspace config is treated as **non-secret** and safe to mount into containers.
- The broker injects tool/model credentials **only** into `isolated` / `host` runner processes.

### Keeping `config.yml` secrets out of containers

Recommended approach: make `config.yml` *not a secrets file*.

- Split “settings” from “secrets”.
  - `config.yml` (or equivalent) may live in the workspace and be mounted into containers.
  - Secrets live in a host-only location that is never mounted into containers.

Fallback (when legacy secrets still exist in workspace files):

- Mask or exclude those files when mounting the workspace (e.g., bind-mount an empty file over `/workspace/config.yml`), and/or run against a projected workspace that excludes dotfiles and known secret files.

For the local MVP, we are **not** introducing a new secret store. The broker reads credentials from the **host process environment** (which can be populated by existing config-loading behavior on the host).

## Canonical Mount Points (avoid path “virtualization”)

To avoid filesystem gymnastics, every execution context should see the same paths:

- Workspace mounted at: `/workspace`
- Tools mounted at: `/tools`

This means:

- Runtime container mounts the host workspace at `/workspace`
- Tool containers (isolated runner) also mount the same host workspace at `/workspace`
- Tool code is mounted read-only at `/tools/<tool-name>`

With consistent mount points, tools don’t need to “guess” where files are, and we don’t need MCP-level path rewriting.

### Path semantics (important)

To keep this simple across all runners (including `host`), we should standardize on:

- **Relative workspace paths only** in tool arguments and in `.tac` code.
- The runtime already wants this for safety (no absolute paths, no traversal).

Then we can make “the same tool works everywhere” true by setting the tool process working directory:

- `sandbox` runner: tool `cwd=/workspace` (inside runtime container)
- `isolated` runner: tool `cwd=/workspace` (inside tool container)
- `host` runner: tool `cwd=<host_workspace_path>` (host filesystem)

This avoids needing to translate `/workspace/...` paths across environments.

Optional but helpful env vars for tool servers:

- `TACTUS_WORKSPACE=/workspace` (or host path for host runner)
- `TACTUS_TOOL_NAME=<name>`
- `TACTUS_TOOL_DIR=/tools/<tool-name>` (or host path if running on host)

## Enforcing a “Secretless” Runtime Container

The goal is not “the agent can’t do bad things”; it’s “the agent can’t obtain long-lived secrets from the runtime container.”

Recommended defaults when launching the runtime container:

- **No host env passthrough**: start from an allowlist; don’t inherit the developer’s shell env.
- **No host home mount**: don’t mount `~` into the container; set `HOME` to a scratch path.
- **No outbound network**: `--network none` for the runtime container; if something needs the network, it should be a brokered capability or an `isolated`/`host` tool.
- **Tool roots are read-only**: mount tool discovery roots read-only so the runtime cannot author new “trusted” tools at runtime.

If you want the runtime container to modify the workspace but still prevent tool-root escalation, use nested mounts:

- Mount workspace `rw` at `/workspace`
- Then re-mount `/workspace/tools*` as `ro` (so the agent can’t write new tool packages into a host-trusted discovery root)

## Tool Runners (Three Modes)

### 1) `sandbox` runner (inside runtime container)

**Use case:** untrusted/community/AI-generated tools that must not see secrets.

- Tool server runs inside the runtime container (stdio)
- No credentials may be injected into this container
- Tools can read/write only inside `/workspace` (and whatever the sandbox allows)

Pros:
- Very simple for local dev
- Strong host protection (tool code trapped in container)

Cons:
- Cannot safely give the tool long-lived secrets

### 2) `isolated` runner (separate tool container)

**Use case:** tools that need credentials, while keeping those credentials out of the runtime container.

- Tool server runs in a separate Docker container (stdio)
- Credentials are injected into the tool container only
- Workspace is mounted into tool container at `/workspace`
- Runtime container calls the broker; broker calls tool container over stdio pipes

Pros:
- Runtime container can’t read tool container env/files, even if runtime escapes Lua sandbox
- Still isolates tool code from the host

Cons:
- Tool code must be treated as privileged (it has credentials, so it can leak/misuse them)

### 3) `host` runner (runs outside Docker)

**Use case:** explicitly trusted tools that need full host access or lower latency.

- Tool server runs on the host under the broker’s supervision
- Credentials can be provided to the host tool process
- Should be opt-in and treated like installing a privileged plugin

Pros:
- Lowest latency
- Easiest integration with host-native services

Cons:
- Not a sandbox; requires explicit trust and careful review

## Tool Auto-Discovery (No “all-or-nothing” config)

We want tools to be available automatically based on where the user puts them.

Proposed convention:

- `./tools/<name>/...` → `sandbox` runner
- `./tools-isolated/<name>/...` → `isolated` runner
- `./tools-host/<name>/...` → `host` runner

Optionally also support user-global roots:

- `~/.tactus/tools/<name>/...` → `sandbox` runner
- `~/.tactus/tools-isolated/<name>/...` → `isolated` runner
- `~/.tactus/tools-host/<name>/...` → `host` runner

Each tool package contains a small manifest (example below) so the platform can reliably start it.

Changing where a tool runs is a filesystem operation the developer controls:

- move/copy `./tools/foo` → `./tools-isolated/foo`

This avoids hidden heuristics about “secretful” vs “non-secretful”.

### Trust boundary (preventing escalation)

Runner selection must not be controllable by untrusted code inside the runtime container.

Concretely:

- The runtime container must not have write access to the host tool roots.
- The easiest safe approach is to mount tools into the runtime container **read-only** at `/tools/...` and mount a separate, per-run working directory at `/workspace` (read-write).
- The broker only discovers tool packages from host-controlled roots and never from writable `/workspace`.

This prevents an agent from writing a “tool package” and tricking the broker into running it as `host`/`isolated` with credentials.

### Tool manifest (minimal)

Example: `mcp.json`

```json
{
  "name": "github",
  "transport": "stdio",
  "command": "node",
  "args": ["server.js"],
  "cwd": "."
}
```

Notes:

- No secrets in the tool package.
- Secrets live in trusted host configuration and are injected only into trusted execution zones (`isolated`/`host`).

## The Broker (RPC + Streaming)

### Transport

- **Local Docker MVP:** stdio (Docker attach), so the runtime container can run with `--network none` even on Docker Desktop.
- **Remote (future):** TCP/TLS (e.g., WebSocket or HTTP/2) with the same NDJSON framing and event semantics.

**Why stdio for the local Docker MVP?**

- Docker Desktop (macOS) does not reliably support bind-mounting a host Unix socket into the container for `asyncio.open_unix_connection` (we hit `OSError: [Errno 95] Operation not supported`).
- Stdio works everywhere Docker attach works and still preserves the core invariant: the runtime container stays **networkless** and **secretless**.
- We use a narrow framing:
  - container → host: broker requests are written to **stderr** as `<<<TACTUS_BROKER>>>{json}`
  - host → container: broker response events are written to **stdin** as NDJSON

### Wire format

- Request: one JSON line (NDJSON), including an `id` for correlation
- Response: a stream of JSON lines (events), ending with `done` or `error`

Example:

```json
{"id":"01JH..","method":"llm.chat","params":{"model":"...","messages":[...]}}
{"id":"01JH..","event":"delta","data":{"text":"Hello"}}
{"id":"01JH..","event":"done"}
```

For long-lived run/event streams (IDE streaming), include a monotonic `seq` per `run_id` so clients can reconnect with `resume_from` and avoid losing streamed output.

### Minimal message types

LLM streaming:

- `llm.chat` → emits `delta` events and then `done`

Tool plumbing:

- `toolsets.list` → returns tool schemas grouped by toolset/server
- `tool.call` (server + tool + args) → returns result (optionally streams logs/progress)

Model invocation:

- `model.invoke` / `model.stream` (same pattern as `llm.chat`)

### Why the broker must be narrow

To avoid the broker becoming an “exfil proxy”, it must not allow arbitrary HTTP:

- no arbitrary base URLs
- no arbitrary headers
- no “fetch this URL” primitive

It should expose only high-level operations (LLM, tool call, model invoke) with allowlists, size limits, timeouts, and audit logging. In particular: no “read config”, no “print env”, no “exec”.

## Broker implementation sketch (focus: MCP stdio tools)

The simplest path is to reuse the existing “stdio MCP server manager” concept:

- Broker maintains a registry of MCP servers (tool packages) that it owns (host + isolated runners).
- Runtime container continues to manage MCP servers that it owns (sandbox runner).

### Key trick: isolated tool containers can still be “stdio”

For isolated tools, we can treat the **Docker CLI** as the “stdio process”:

- The broker runs `docker run --rm -i ... <tool-server-command>`
- `docker run -i` connects the container’s stdin/stdout to the `docker` process
- From the broker’s perspective, that’s just a normal stdio child process

That means the broker can speak MCP over stdio to an isolated tool container without inventing any new transport.

This is a great **local** implementation strategy. For cloud orchestrators (ECS/Fargate/EKS), there is no equivalent “attach to task stdio”, so the `isolated` runner will need a different backend:

- run a small **tool-runner shim** next to the stdio tool server that bridges **network ⇄ stdio**, or
- package tools as network-native servers (optional), and have the broker connect over the network.

Example (conceptual) stdio command for an isolated tool:

```bash
docker run --rm -i \
  --network none \
  -v "<host_workspace>:/workspace:rw" \
  -v "<host_tools_isolated>/github:/tools/github:ro" \
  -w /workspace \
  -e TACTUS_WORKSPACE=/workspace \
  -e GITHUB_TOKEN=... \
  tactus/tool-runner:latest \
  node /tools/github/server.js
```

Note: `--network none` is ideal when a tool does not need egress. Tools that need outbound access will require enabling it, which also creates an exfiltration channel.

### Broker responsibilities (per `tactus run`)

1. Load trusted host configuration (keys, tool creds, policy)
2. Discover tool packages from trusted roots (`tools/`, `tools-isolated/`, `tools-host/`)
3. Start and manage tool servers for `isolated` and `host` runners
4. Expose remote tool schemas and tool calls to the runtime container over broker RPC
5. Perform LLM/model calls on behalf of the runtime (streaming)

### Runtime container responsibilities

1. Start and manage `sandbox` runner MCP servers (from `/tools/...`)
2. Ask broker for remote tool schemas (`isolated` and `host`) and register wrapper tools
3. On tool invocation, call either:
   - the local MCP server directly (`sandbox`), or
   - the broker (`isolated`/`host`)

### How remote tools appear to the agent (no MCP tunneling)

The runtime container does *not* need to speak MCP to remote tools.

Instead:

- On startup, runtime calls `broker.toolsets.list` (or equivalent).
- Broker returns `{server_name, tools:[{name, description, inputSchema}, ...]}`.
- Runtime generates PydanticAI `Tool`s that call `broker.tool.call(server_name, tool_name, args)`.

This mirrors what an MCP adapter would do, but without passing MCP frames across the container boundary.

### Suggested broker RPC operations (minimal)

- `toolsets.list` → list remote toolsets + tool schemas
- `tool.call` → call a specific tool (request/response; optionally streamed logs)
- `llm.chat` → streamed LLM responses (delta events)
- `model.invoke` / `model.stream` → model inference (optional streaming)

## “Virtualizing” MCP stdio tools across runners

Key design choice: the runtime container should not need to speak MCP to tools that run outside the container.

Instead:

1. Broker starts MCP server processes (host runner) or tool containers (isolated runner)
2. Broker speaks MCP over stdio to those servers
3. Runtime container calls the broker’s `toolsets.list` and `tool.call` RPCs
4. Runtime exposes those remote tools to the agent as normal tool definitions

This keeps the runtime simple and avoids needing to tunnel stdio across container boundaries.

For `sandbox` runner tools, the runtime can continue to use direct stdio via existing MCP plumbing, since they’re already co-located.

## Docker layers (what they help with, and what they don’t)

Docker layers don’t remove the need for a broker or for consistent mount points. Where they *do* help:

- Provide a stable base image for tool containers (Python + Node + common deps) so most tools can run by mounting code at `/tools/<name>`.
- Cache expensive dependency installs when building dedicated images for heavy tools.

Default recommendation for simplicity:

- A single `tactus/tool-runner` image that can execute `node ...` and `python ...`, with tool code mounted read-only.

## Running Without Docker (same code path)

We still want the same API surface even when Docker is disabled:

- Runtime uses a `BrokerClient` interface in all modes
- In “no Docker” mode, the broker can run:
  - in-process as a `LocalBackend` (no IPC), but still emitting the same event stream shape
  - (optional) as a local subprocess with stdio framing

The important part is that the runtime calls the same `BrokerClient` methods, regardless of deployment mode.

## Execution Backends (Local vs Remote)

The plan above assumes **full isolation by default** (one worker per run), but we should design the broker protocol so other deployment choices don’t require rewriting the runtime or tools.

### Worker lifetime policies (deployment choice)

- **Per-run worker** (default): strongest isolation; highest startup overhead.
- **Warm pool**: keep N workers prestarted; assign runs to an available worker; periodically recycle workers.
- **Shared worker**: run many invocations in one long-lived worker; lowest overhead; weakest isolation (requires strong per-run process/workspace cleanup).

Key requirement: the broker (and IDE clients) must assume `run_id` is a **logical session**, not “the container id”.

### Local Docker

- Broker runs on the host.
- Worker(s) are Docker containers (per-run, pooled, or shared).
- Runtime ↔ broker uses **stdio attach** for local MVP (no container networking required).

### Orchestrated workers (ECS/Fargate/EKS)

- Broker runs as a long-lived service.
- Workers are tasks/pods that connect **outbound** to the broker over TCP/TLS (same protocol framing).
- Workspace distribution shifts from bind-mounts to S3 sync or EFS, but we preserve the `/workspace` + relative-path conventions.
- The `isolated` tool runner cannot rely on Docker stdio attach; it needs a network-capable tool runner (shim/service) as noted above.

### `host` runner semantics in cloud

In cloud deployments, “host runner” usually means “broker-local trusted code” (plugins/builtins), not “execute arbitrary workspace code next to secrets”.

## Milestones (Implementation Plan)

This started as a “vision” doc; the steps below turn it into a phased implementation plan with an explicit **Local-first** phase and an **AWS-early** phase.

### Phase 1A: Local Docker MVP (Primary Goal)

Goal: on a laptop with Docker, run procedures with a **secretless + networkless runtime container** and a **host broker** that performs **OpenAI LLM calls** with **end-to-end streaming**.

Deliverables:

1. **Runtime container hardening**
   - Runtime container runs with `--network none`
   - No credential passthrough env vars (OpenAI/AWS/etc)
   - No secrets passed via the execution request payload
2. **Broker RPC + streaming (stdio)**
   - Stdio transport (host broker ↔ runtime container via Docker attach)
   - Minimal message types: `llm.chat` (streaming) + `events.emit` (log relay)
3. **Brokered OpenAI provider**
   - Runtime uses broker for all OpenAI LLM calls
   - Container has no OpenAI key and no outbound network
4. **Streaming without container networking**
   - Replace HTTP callback streaming with stdio event relay via the broker
5. **Tests**
   - Streaming regression tests for brokered `llm.chat`
   - “Secrets never enter runtime container” invariants (env + request payload)

Acceptance / validation (manual):

- `tactus sandbox rebuild --force`
- `tactus run examples/53-tsv-file-io.tac --sandbox --verbose` (no LLM/network)
- `tactus run examples/06-basics-streaming.tac --sandbox --verbose` (requires host OpenAI credentials; container still runs `--network none`)

### Phase 1B: Host Tools (Deferred, Local Only)

Goal: allow explicitly trusted tools to run on the host under the broker, without introducing tool discovery/manifests yet.

Deliverables (minimum viable):

1. A small allowlisted “host tool” registry owned by the broker
2. `tool.call` RPC for those tools
3. Basic tool call auditing (names + args sizes + durations)

Implementation note (current WIP):

- The broker protocol includes `tool.call` and the runtime container exposes a `Host` primitive (`Host.call(name, args)`) that routes via the broker. The initial allowlist is intentionally tiny and deny-by-default.

Recommended next step (implementation order):

1. Add `tool.call` RPC and a minimal allowlisted registry (e.g., `host.ping`, `host.read_text` with strict path allowlist).
2. Add a Lua DSL/tool “source” for broker tools (e.g., `source = "broker.host.ping"` or a dedicated `BrokerTool{...}` constructor).
3. Add tests that prove:
   - runtime cannot access host env/secrets
   - broker tool calls are allowlisted (deny-by-default)
   - tool call audit events stream back via `events.emit`

### Phase 1C: Isolated Tool Runner (Deferred)

Goal: run credentialed tools in a separate container (`isolated`), still without secrets entering the runtime container.

Deliverables:

1. Broker launches `docker run -i ...` tool containers and speaks MCP over stdio
2. Policy: which tools are allowed to run isolated, and which env vars they can receive

### Phase 2: Remote-Mode Spike (Before AWS)

Goal: validate the architecture is cloud-ready **without** requiring AWS on day 1.

Deliverables:

1. **TCP/TLS broker transport**
   - Run broker as a host process listening on localhost (or LAN) with TLS (self-signed is fine for the spike)
2. **Remote worker connectivity**
   - Run the runtime container in a way that forces network transport (no stdio attach)
   - Confirm IDE streaming works over the same run stream protocol (`run_id`/`seq`/resume)

This phase is intentionally “small but real”: it confirms we didn’t accidentally design around stdio-only assumptions.

Local spike validation (CLI):

- `tactus run examples/53-tsv-file-io.tac --sandbox --sandbox-broker tcp --verbose`
- `tactus run examples/06-basics-streaming.tac --sandbox --sandbox-broker tcp --verbose`

Notes:

- This uses Docker `--network bridge` so the runtime can reach the broker over TCP. In real deployments, you enforce “runtime can only talk to broker” using K8s NetworkPolicy / security groups.

### Phase 3: AWS Execution (ECS/Fargate) (Early, Not Last)

Goal: prove we can execute the same runtime worker in AWS with interactive IDE streaming, using the same broker protocol.

Deliverables (minimum viable):

1. **Broker runs as a service**
   - Holds secrets (AWS Secrets Manager or env injection), exposes streaming endpoints
2. **Worker runs as ECS task / Fargate**
   - Worker connects outbound to broker over TCP/TLS and streams events
3. **Workspace distribution**
   - Choose one: S3 sync (simple) or EFS (mount-like)
4. **Isolated tool runner backend (remote)**
   - Replace “docker stdio attach” with a network-capable tool runner:
     - tool-runner shim bridges network ⇄ stdio MCP inside the task/pod, or
     - tools become network-native servers (optional)

We should treat “AWS” as a backend implementation of:

- `RunRunner` (local docker vs ECS)
- tool runner backend (`isolated` local docker-stdio vs remote tool-runner shim)
- workspace provider (bind-mount vs S3/EFS)

### Phase 4: Azure / Other Orchestrators (Optional)

Goal: reuse Phase 2/3 abstractions to add another backend (AKS/Kubernetes, Azure Container Apps, etc.) without changing the runtime/tool APIs.

## Open Questions

- Container model: one tool container per tool server, or a shared “tool runner” container per run?
- How do we want to expose tool logs/stdio to the IDE (streamed events vs only final result)?
- How do we name/version tool packages and manifests (for portability)?
- What’s the minimum viable “policy layer” we want in the broker (allowlists, budgets, audit logging)?
