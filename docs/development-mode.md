# Development Mode for Sandbox Container

## Problem

During development, the Tactus sandbox container has the Tactus code baked in at build time. This means:
- Every code change requires rebuilding the container
- Forgetting to rebuild causes obscure errors from version mismatches
- Development iteration is slow

## Solution: Development Mode with Live Mounting

Development mode (`dev_mode: true`) mounts your local Tactus source code into the container at runtime instead of using the baked-in version.

### How It Works

When `dev_mode` is enabled, the container runner:
1. Detects the location of your Tactus repository
2. Mounts the `tactus/` directory into the container at `/app/tactus`
3. Python's editable install (`pip install -e .`) picks up the live code

This means code changes are **immediately available** in the container without rebuilding.

### Automatic Repository Detection

**Important:** The detection happens on the **host machine** (where `tactus` CLI or IDE is running), not inside the container.

The system automatically finds your Tactus repository in this order:

1. **`TACTUS_DEV_PATH` environment variable** (explicit override)
   ```bash
   export TACTUS_DEV_PATH=/path/to/Tactus
   ```

2. **Python module location** (if installed with `pip install -e .`)
   - When you run `pip install -e .` from a Tactus repo, Python remembers where the source is
   - The code reads `tactus.__file__` which points to the actual `.py` file location
   - Example: If `tactus` was installed from `/Users/you/Projects/Tactus`, then:
     - `tactus.__file__` → `/Users/you/Projects/Tactus/tactus/__init__.py`
     - Repo root → `/Users/you/Projects/Tactus`
   - This works **even if you run from a different directory**

3. **Current working directory** (if it contains `tactus/` and `pyproject.toml`)
   - Only used if methods 1 and 2 fail

### How Does This Work Remotely?

**Scenario 1: Development from Tactus repo**
- You: Clone Tactus, run `pip install -e .`, start IDE from anywhere
- Detection: Method #2 finds it via `tactus.__file__`
- Result: ✅ Dev mode works

**Scenario 2: Installed from PyPI (`pip install tactus`)**
- You: Client project, no Tactus repo nearby
- Detection: `tactus.__file__` points to site-packages (not a repo)
- Result: ❌ Dev mode cannot find source, falls back to baked-in version

**Scenario 3: Multiple Tactus clones**
- You: Have Tactus installed in multiple locations
- Detection: Uses whichever one Python loads (first in `sys.path`)
- Override: Set `TACTUS_DEV_PATH` to choose explicitly

### When Dev Mode is Enabled

**IDE (tactus-ide)**: Dev mode is **automatically enabled** by default.

**CLI**: Enable via config or environment:
```bash
# Via environment variable
export TACTUS_SANDBOX_DEV_MODE=true
tactus run procedure.tac

# Via config file (.tactus.toml)
[sandbox]
dev_mode = true
```

### When to Use Each Mode

| Mode | Use Case | Rebuild Needed? |
|------|----------|----------------|
| **Dev Mode (dev_mode: true)** | Active development, testing changes | No - code is live mounted |
| **Production Mode (dev_mode: false)** | Released containers, CI/CD, client usage | Yes - code is baked in |

### Limitations

**Dev mode only works when:**
- Tactus was installed via `pip install -e .` from a repo clone
- Or `TACTUS_DEV_PATH` environment variable is set
- Or running from within a Tactus repository directory

**If running from a client project with PyPI-installed Tactus:**
- Dev mode cannot find the source (no repo exists)
- Gracefully falls back to using the baked-in version
- Container must be rebuilt to update (but this is expected for production use)

**The key benefit:** For Tactus developers (using `pip install -e .`), dev mode works **everywhere** - you don't need to `cd` into the repo or rebuild containers during development.

### Logs

When dev mode activates, you'll see:
```
INFO:tactus.sandbox.container_runner:[DEV MODE] Mounting live Tactus source from: /path/to/Tactus
```

If it can't find the source:
```
WARNING:tactus.sandbox.container_runner:[DEV MODE] Could not locate Tactus source directory, using baked-in version
```

## Initial Container Build

You still need to build the container once initially to get the base dependencies:
```bash
docker build -t tactus-sandbox:local -f tactus/docker/Dockerfile .
```

But after that, code changes are instantly available with dev mode enabled.

## Future Enhancement: Published Containers

For production use cases, Tactus could publish versioned containers to Docker Hub:
- `anthus/tactus-sandbox:0.26.0`
- `anthus/tactus-sandbox:latest`

Users would then:
- Pull the appropriate version: `docker pull anthus/tactus-sandbox:0.26.0`
- Set `sandbox.image: "anthus/tactus-sandbox:0.26.0"` in their config
- Never need to build containers themselves
