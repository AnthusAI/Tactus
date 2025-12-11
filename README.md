# Tactus

**Tactus**: A Lua-based DSL for defining and executing agentic workflows.

> **⚠️ Status: Alpha** - Tactus is in early development. Only a subset of the [specification](SPECIFICATION.md) is currently implemented. See [IMPLEMENTATION.md](IMPLEMENTATION.md) for details on what's complete and what's missing. The API is subject to change.

Tactus implements the **"Give an Agent a Tool"** programming paradigm: instead of writing explicit code to handle every edge case, you define capabilities (tools) and goals, then let an intelligent agent figure out how to use them to solve the problem.

## Philosophy & Research

Tactus is built on two core insights into the future of AI software:

### 1. The "Give an Agent a Tool" Paradigm
Traditional programming requires anticipating every edge case. Tactus shifts this burden by allowing you to define **capabilities (tools)** and **goals**, letting the agent figure out the execution details.
> *"If you give an agent a tool, then nobody has to fish."*
- **Read**: [Give an Agent a Tool](https://anth.us/blog/give-an-agent-a-tool/) (Anthus)
- **Demo**: [AnthusAI/Give-an-Agent-a-Tool](https://github.com/AnthusAI/Give-an-Agent-a-Tool)

### 2. Production Reality: Control > Autonomy
Recent large-scale studies of agents in production reveal that successful systems rely on **constrained deployment**, **bounded autonomy**, and **human oversight** rather than open-ended "magic".
- **Read**: [Measuring Agents in Production](https://arxiv.org/abs/2512.04123) (UC Berkeley, et al.)

**Tactus aligns with these production realities:**
- **Controllability**: Unlike black-box frameworks, Tactus uses Lua to define explicit, bounded control flow (loops, conditionals).
- **Human-in-the-Loop**: First-class primitives (`Human.approve`, `Human.input`) are built into the core, not added as afterthoughts.
- **Simplicity**: A lightweight DSL that prioritizes reliability over open-ended "self-planning".

## Features

- **Declarative Workflows**: Define agent workflows in YAML with embedded Lua code
- **Pluggable Backends**: Storage, HITL, and chat recording via Pydantic protocols
- **Human-in-the-Loop**: Built-in support for human approval, input, and review
- **LLM Integration**: Works with OpenAI models via [pydantic-ai](https://github.com/pydantic/pydantic-ai)
- **Checkpointing**: Automatic workflow checkpointing and resume
- **Standalone CLI**: Run workflows without any infrastructure
- **Type-Safe**: Pydantic models throughout for validation and type safety

**Note**: Some features from the [specification](SPECIFICATION.md) are not yet implemented, including `guards`, `dependencies`, inline procedure definitions, and advanced HITL configuration. See [IMPLEMENTATION.md](IMPLEMENTATION.md) for the complete status.

## Quick Start

### Installation

```bash
pip install tactus
```

### Your First Workflow: Giving an Agent a Tool

Here is a minimal example. We give the agent a single tool (`done`) and a goal ("Greet the user"). The agent decides when and how to call the tool.

Create a file `hello.yaml`:

```yaml
name: hello_world
version: 1.0.0
class: LuaDSL

params:
  name:
    type: string
    default: "World"

# 1. Define the Agent and its Tools
agents:
  greeter:
    system_prompt: |
      You are a friendly greeter. Greet the user by name: {params.name}
      When done, call the done tool.
    
    initial_message: "Please greet the user."
    
    # The agent uses this tool to signal completion
    tools:
      - done

# 2. Define the Orchestration Logic (Lua)
procedure: |
  -- Loop until the agent decides to use the 'done' tool
  repeat
    Greeter.turn()
  until Tool.called("done")

  -- Return the result captured from the tool call
  return {
    completed = true,
    greeting = Tool.last_call("done").args.reason
  }
```

Run it:

```bash
export OPENAI_API_KEY=your-key
tactus run hello.yaml
```

## Architecture

Tactus is built around three core abstractions:

1. **StorageBackend**: Persists procedure state and checkpoints
2. **HITLHandler**: Manages human-in-the-loop interactions
3. **ChatRecorder**: Records conversation history

These are defined as Pydantic protocols, allowing you to plug in any implementation:

```python
from tactus import TactusRuntime
from tactus.adapters.memory import MemoryStorage
from tactus.adapters.cli_hitl import CLIHITLHandler

runtime = TactusRuntime(
    procedure_id="my-workflow",
    storage_backend=MemoryStorage(),
    hitl_handler=CLIHITLHandler(),
    chat_recorder=None  # Optional
)

result = await runtime.execute(yaml_config, context)
```

## CLI Commands

```bash
# Run a workflow
tactus run workflow.yaml
tactus run workflow.yaml --param task="Analyze data"
# ...
```

## Documentation

- [**Specification (DSL Reference)**](SPECIFICATION.md) - The official specification for the Tactus domain-specific language.
- [**Implementation Guide**](IMPLEMENTATION.md) - Maps the specification to the actual codebase implementation. Shows where each feature is implemented, what's complete, and what's missing relative to the specification.
- [**Examples**](examples/) - Run additional example procedures to see Tactus in action
- **Primitives Reference** (See `tactus/primitives/`)
- **Storage Adapters** (See `tactus/adapters/`)

## Integration

Tactus is designed to be integrated into larger systems. You can create custom adapters for your storage backend, HITL system, and chat recording.

## Development

```bash
# Clone the repository
git clone https://github.com/AnthusAI/Tactus.git
cd Tactus

# Install with dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run with coverage
pytest --cov=tactus --cov-report=html
```

## License

MIT License - see LICENSE file for details.
