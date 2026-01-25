# Tactus Configuration Guide

This guide explains how Tactus loads and merges configuration from multiple sources.

## Configuration Cascade

Tactus uses a **cascading configuration system** where settings from multiple sources are merged together, with clear priority ordering.

### Priority Order (Highest to Lowest)

1. **CLI Arguments** - Command-line parameters (e.g., `--param key=value`)
2. **Sidecar Config** - `procedure.tac.yml` next to your `.tac` file
3. **Local Directory Config** - `.tactus/config.yml` in the procedure's directory
4. **Parent Directory Configs** - `.tactus/config.yml` files walking up the tree
5. **Project Config** - `.tactus/config.yml` in the current working directory
6. **User Config** - `~/.tactus/config.yml` (also supports XDG: `~/.config/tactus/config.yml`)
7. **System Config** - `/etc/tactus/config.yml` (and `/usr/local/etc/tactus/config.yml`)
8. **Environment Variables** - System environment variables (fallback)

### How Merging Works

- **Simple values** (strings, numbers, booleans): Higher priority overwrites lower priority
- **Lists**: Extended (combined) - items from all levels are included
- **Dictionaries**: Deep merged - nested keys are combined

## Configuration Files

### User Configuration (`~/.tactus/config.yml`)

Use a user-wide config if you want to install Tactus once and run it from any directory.

**Location**: `~/.tactus/config.yml` (also supports XDG: `~/.config/tactus/config.yml`)

**Example**:
```yaml
# API Keys (sensitive - keep private)
openai_api_key: "sk-..."
```

### Project Configuration (`.tactus/config.yml`)

The project configuration file contains settings scoped to a repository/directory tree.

**Location**: `.tactus/config.yml` in your project root

**Example**:
```yaml
# API Keys (sensitive - keep in .gitignore)
openai_api_key: "sk-..."

# AWS Credentials
aws:
  access_key_id: "..."
  secret_access_key: "..."
  default_region: "us-east-1"

# Common tool paths (shared across all procedures)
tool_paths:
  - "./common_tools"
```

**Security**: This file often contains secrets. Add it to `.gitignore`:
```
.tactus/config.yml
```

### Sidecar Configuration (`procedure.tac.yml`)

Sidecar configs contain **procedure-specific settings** that sit next to your `.tac` file.

**Naming Convention**:
- Preferred: `{procedure}.tac.yml` (e.g., `mortgage.tac.yml` for `mortgage.tac`)
- Alternative: `{procedure}.yml` (e.g., `mortgage.yml`)

**Example** (`examples/mortgage.tac.yml`):
```yaml
# Procedure-specific configuration
# This file is NOT sandboxed - keep it trusted!

# Additional tool paths for this procedure
tool_paths:
  - "./examples/tools"

# Override model for this specific procedure
default_model: "gpt-4o-mini"

# Optional: procedure-specific MCP servers
# mcp_servers:
#   custom:
#     command: "node"
#     args: ["./custom-server.js"]
```

**Security**: Sidecar files can contain file paths and command execution. Only use trusted sidecar files.

## Sandbox Configuration

Tactus runs procedures in Docker containers by default for security isolation. You can configure sandbox behavior at any configuration level (user, project, or sidecar).

### Basic Sandbox Settings

```yaml
# ~/.tactus/config.yml or .tactus/config.yml
sandbox:
  enabled: true                    # Default (CLI): require Docker sandbox
  image: "tactus-sandbox:local"    # Docker image name (auto-built on first use)
  timeout: 3600                    # Max execution time in seconds (default: 1 hour)
  mcp_servers_path: "~/.tactus/mcp-servers"  # Path to MCP servers
```

**Note**: If Docker is unavailable and `enabled: true`, execution will fail with an error. Use `--no-sandbox` or set `enabled: false` to explicitly run without isolation.

### Sandbox Image Build Modes

Tactus auto-builds the sandbox image the first time you run a procedure with Docker:

- **Source tree available**: the image bakes in the local Tactus source.
- **PyPI install only**: the image installs the same published Tactus version from PyPI.

This means `pip install tactus` plus `Tactus-examples` works without needing a full Tactus repo checkout.

### Resource Limits

Control memory and CPU usage per container:

```yaml
sandbox:
  limits:
    memory: "2g"     # Per-container memory limit (default: 2GB)
    cpus: "2"        # Per-container CPU cores (default: 2)
```

**Error handling**:
- Out of memory: Container killed with exit code 137
- Timeout exceeded: Container killed with exit code 124

### Network Configuration

Control network access for procedures:

```yaml
sandbox:
  network: "none"  # Network mode (default: none)

  # Options:
  # - "bridge": Default Docker bridge (allows outbound connections)
  # - "none": No network access in the runtime container (most secure)
  # - "host": Use host network (not recommended for security)
  # - "custom-network": Use a custom Docker network
```

With the brokered sandbox runtime, `network: none` can still support LLM calls because the runtime talks to a host-side broker over the configured broker transport (default: `stdio`).

If you enable runtime networking (`network != none`), treat that as higher risk and enforce egress controls so the runtime can only reach the broker. See [Sandboxing Guide: Threat Model](./SANDBOXING.md#threat-model).

### Broker Transport

Control how the secretless runtime container communicates with the host broker:

```yaml
sandbox:
  broker_transport: "stdio"  # default (works with network: none)
```

Options:
- `stdio`: Local Docker MVP; container stays networkless and communicates via the docker attach stdio channel
- `tcp`: Remote-style connectivity; requires `sandbox.network != none`
- `tls`: Same as `tcp` but wrapped in TLS; requires `sandbox.network != none`

### Volume Mounts

**Default behavior**: Tactus automatically mounts your current directory to `/workspace:rw`, making it easy for procedures to read and write project files. This is safe because:
- Container isolation prevents access outside the mounted directory
- Git provides version control and rollback capability
- You can review all changes before committing

To disable the default mount:

```yaml
sandbox:
  mount_current_dir: false  # Disable automatic current directory mount
```

**Additional volume mounts**: Mount other host directories into the container:

```yaml
sandbox:
  volumes:
    - "/host/data:/data:ro"           # Read-only mount
    - "/host/outputs:/outputs:rw"     # Read-write mount
    - "../other-repo:/external:ro"    # Relative paths supported
```

**Path resolution**:
- Relative paths (e.g., `./data`, `../repo`) resolve from the procedure directory
- `~` expands to your home directory
- Absolute paths used as-is

**Volume modes**:
- `:ro` - Read-only (safer when you don't need writes)
- `:rw` - Read-write (default if not specified)

**Default mounts** (always included):
- Current directory: `.:/workspace:rw` (unless `mount_current_dir: false`)
- MCP Servers: `~/.tactus/mcp-servers` at `/mcp-servers` (read-only, if exists)

### Environment Variables

Pass environment variables to the container:

```yaml
sandbox:
  env:
    CUSTOM_VAR: "value"
    DEBUG: "true"
    LOG_LEVEL: "info"
```

Tactus intentionally blocks common secret env vars from entering the runtime container. For LLM calls, provide credentials to the host/broker side (for example via your shell environment or host-side config loading), not via `sandbox.env`.

### Per-Procedure Sandbox Configuration

Use sidecar files to customize sandbox settings per procedure:

**Example**: `financial_analysis.tac.yml`
```yaml
# Procedure-specific sandbox configuration
sandbox:
  enabled: true

  limits:
    memory: "4g"      # More memory for data-heavy processing
    cpus: "4"         # More CPU cores

  timeout: 1800       # 30 minute timeout

  network: "none"     # No network access for sensitive data

  volumes:
    - "/data/financial:/data:ro"      # Read-only financial data
    - "/output/reports:/reports:rw"   # Write reports here

  env:
    DATA_PATH: "/data"
    OUTPUT_PATH: "/reports"
```

**Use cases for per-procedure sandbox configs**:
- Higher resource limits for data-intensive procedures
- Network isolation for procedures handling sensitive data
- Custom volume mounts for specific data sources
- Procedure-specific environment variables

### Disabling the Sandbox

To run without Docker isolation:

**Via CLI**:
```bash
tactus run procedure.tac --no-sandbox
```

**Via configuration**:
```yaml
sandbox:
  enabled: false
```

**Security warning**: Running without sandbox removes OS-level isolation. Only disable for trusted procedures or development. See [Sandboxing Guide](./SANDBOXING.md) for security implications.

### Directory-Level Configuration

You can place `.tactus/config.yml` files in any directory to configure settings for procedures in that directory and subdirectories.

**Example structure**:
```
project/
  .tactus/
    config.yml          # Root config (API keys)
  examples/
    .tactus/
      config.yml        # Config for all examples
    mortgage.tac
    mortgage.tac.yml    # Sidecar for specific procedure
```

## Configuration Examples

### Example 1: Simple Sidecar

**File**: `examples/calculator.tac.yml`
```yaml
tool_paths:
  - "./examples/tools"
```

**Result**: Procedure uses tools from `./examples/tools` in addition to any tools from root config.

### Example 2: Override Model

**Root config** (`.tactus/config.yml`):
```yaml
default_model: "gpt-4o"
```

**Sidecar** (`quick_task.tac.yml`):
```yaml
default_model: "gpt-4o-mini"
```

**Result**: This specific procedure uses `gpt-4o-mini` instead of the default `gpt-4o`.

### Example 3: Extend Tool Paths

**Root config**:
```yaml
tool_paths:
  - "./common_tools"
```

**Directory config** (`examples/.tactus/config.yml`):
```yaml
tool_paths:
  - "./examples/shared_tools"
```

**Sidecar** (`examples/mortgage.tac.yml`):
```yaml
tool_paths:
  - "./examples/tools"
```

**Result**: Procedure has access to all three tool paths:
- `./common_tools` (from root)
- `./examples/shared_tools` (from directory)
- `./examples/tools` (from sidecar)

### Example 4: CLI Override

```bash
# Root config has default_model: "gpt-4o"
# Sidecar has default_model: "gpt-4o-mini"

# CLI argument overrides everything:
tactus run procedure.tac --param model="gpt-3.5-turbo"
```

**Result**: Uses `gpt-3.5-turbo` (CLI takes precedence).

## Security Considerations

### Safe: `.tac` Files

`.tac` files contain **sandboxed Lua code** and are safe for:
- User contributions
- AI generation
- Sharing publicly

**Never put configuration in `.tac` files** - they should remain pure code.

### Trusted: Configuration Files

Configuration files (`.yml`) can contain:
- API keys
- File paths
- Command execution
- MCP server definitions

**Only use trusted configuration files** from sources you control.

### Recommended `.gitignore`

```
# Ignore root config (contains secrets)
.tactus/config.yml

# Optionally ignore sidecar configs if they contain secrets
*.tac.yml
```

## Environment Variables

Tactus reads these environment variables as fallback configuration:

- `OPENAI_API_KEY` - OpenAI API key
- `GOOGLE_API_KEY` - Google Gemini API key
- `AWS_ACCESS_KEY_ID` - AWS access key
- `AWS_SECRET_ACCESS_KEY` - AWS secret key
- `AWS_DEFAULT_REGION` - AWS region
- `TOOL_PATHS` - JSON array of tool paths (e.g., `'["./tools"]'`)

Environment variables have the **lowest priority** and are overridden by any config file.

## Best Practices

### 1. Separate Secrets from Code

**Do**:
- Keep API keys in a Tactus config file (user-wide or project-specific)
- Add `.tactus/config.yml` to `.gitignore`
- Use environment variables in CI/CD

**Don't**:
- Put secrets in sidecar configs that are committed to git
- Put configuration in `.tac` files

### 2. Use Sidecar Configs for Procedure-Specific Settings

**Good use cases**:
- Tool paths specific to a procedure
- Model overrides for specific tasks
- Procedure-specific MCP servers

**Example**:
```yaml
# mortgage_calculator.tac.yml
tool_paths:
  - "./financial_tools"
default_model: "gpt-4o-mini"  # Cheaper model for simple math
```

### 3. Use Directory Configs for Shared Settings

If multiple procedures in a directory share settings, use a directory-level config:

```
examples/
  .tactus/
    config.yml         # Shared by all examples
  mortgage.tac
  loan.tac
  investment.tac
```

### 4. Document Configuration Requirements

In your procedure comments, document what configuration is needed:

```lua
--[[
Mortgage Calculator

Configuration required:
- tool_paths: Must include "./financial_tools"
- openai_api_key: Required for LLM calls

See mortgage.tac.yml for example configuration.
]]--
```

## Troubleshooting

### Configuration Not Loading

**Check**:
1. File exists and has correct name (`.tac.yml` or `.yml`)
2. YAML syntax is valid (use a YAML validator)
3. File is in the correct location (same directory as `.tac` file)
4. Run with `--verbose` to see config loading messages

### Lists Not Extending

Lists are automatically extended (combined) from all config levels. If you see unexpected behavior:

1. Check for duplicate entries (duplicates are removed)
2. Verify the list key name is consistent across configs
3. Use `--verbose` to see the merged configuration

### Priority Not Working

Remember the priority order:
1. CLI args (highest)
2. Sidecar
3. Local directory
4. Parent directories
5. Root
6. Environment (lowest)

If a value isn't being used, check if it's being overridden by a higher-priority source.

## Advanced: Programmatic Usage

You can use the configuration manager directly in Python:

```python
from pathlib import Path
from tactus.core.config_manager import ConfigManager

# Load configuration cascade
config_manager = ConfigManager()
config = config_manager.load_cascade(Path("procedure.tac"))

# Access merged configuration
tool_paths = config.get("tool_paths", [])
api_key = config.get("openai_api_key")
```

## See Also

- [Sandboxing & Security](SANDBOXING.md) - Security concepts and threat models
- [Tool Roadmap](TOOL_ROADMAP.md) - Information about tool loading
- [README](../README.md) - General Tactus documentation
- [Examples](../examples/) - Example procedures with sidecar configs
