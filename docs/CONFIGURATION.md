# Tactus Configuration Guide

This guide explains how Tactus loads and merges configuration from multiple sources.

## Configuration Cascade

Tactus uses a **cascading configuration system** where settings from multiple sources are merged together, with clear priority ordering.

### Priority Order (Highest to Lowest)

1. **CLI Arguments** - Command-line parameters (e.g., `--param key=value`)
2. **Sidecar Config** - `procedure.tac.yml` next to your `.tac` file
3. **Local Directory Config** - `.tactus/config.yml` in the procedure's directory
4. **Parent Directory Configs** - `.tactus/config.yml` files walking up the tree
5. **Root Config** - `.tactus/config.yml` in project root (current working directory)
6. **Environment Variables** - System environment variables (fallback)

### How Merging Works

- **Simple values** (strings, numbers, booleans): Higher priority overwrites lower priority
- **Lists**: Extended (combined) - items from all levels are included
- **Dictionaries**: Deep merged - nested keys are combined

## Configuration Files

### Root Configuration (`.tactus/config.yml`)

The root configuration file contains **shared settings** like API keys and common tool paths.

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
- `AWS_ACCESS_KEY_ID` - AWS access key
- `AWS_SECRET_ACCESS_KEY` - AWS secret key
- `AWS_DEFAULT_REGION` - AWS region
- `TOOL_PATHS` - JSON array of tool paths (e.g., `'["./tools"]'`)

Environment variables have the **lowest priority** and are overridden by any config file.

## Best Practices

### 1. Separate Secrets from Code

**Do**:
- Keep API keys in root `.tactus/config.yml`
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

- [Tool Roadmap](TOOL_ROADMAP.md) - Information about tool loading
- [README](../README.md) - General Tactus documentation
- [Examples](../examples/) - Example procedures with sidecar configs

