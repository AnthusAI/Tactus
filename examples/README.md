# Tactus Examples

This directory contains example Tactus procedure files that demonstrate how to use the Tactus Lua DSL.

## Running Examples

Each example can be run directly with the Tactus CLI:

```bash
tactus run examples/hello-world.tac
tactus run examples/with-parameters.tac --param task="My task" --param count=10
```

## Example Files

### hello-world.tac

A basic "Hello World" example that demonstrates:
- Simple workflow execution
- State management with State primitive
- Logging operations
- Output schema validation

**Run:**
```bash
tactus run examples/hello-world.tac
```

### state-management.tac

Demonstrates state operations:
- Setting and getting state values
- Incrementing numeric state
- Iterating with state tracking
- Returning structured output

**Run:**
```bash
tactus run examples/state-management.tac
```

### with-parameters.tac

Shows how to use parameters:
- Declaring parameters with types and defaults
- Accessing parameters in workflow code
- Overriding parameters via CLI

**Run:**
```bash
# Use defaults
tactus run examples/with-parameters.tac

# Override parameters
tactus run examples/with-parameters.tac --param task="Custom task" --param count=5
```

### simple-agent.tac

Demonstrates agent interaction:
- Defining agents with system prompts
- Agent turns and tool calls
- LLM integration with OpenAI
- Structured output from agent responses

**Run:**
```bash
tactus run examples/simple-agent.tac
```

### multi-model.tac

Shows multi-model configuration:
- Using different models for different agents
- Model-specific parameters (temperature, max_tokens)
- Default provider and model settings

**Run:**
```bash
tactus run examples/multi-model.tac
```

## Configuration

Some examples require configuration, particularly LLM-based examples that need an OpenAI API key.

### Setting Up Configuration

1. Create a `.tac` directory in your project root:
   ```bash
   mkdir -p .tac
   ```

2. Copy the example config file:
   ```bash
   cp examples/.tac/config.yml.example .tac/config.yml
   ```

3. Edit `.tac/config.yml` and add your OpenAI API key:
   ```yaml
   openai_api_key: "sk-your-actual-api-key-here"
   ```

4. Add `.tac/config.yml` to your `.gitignore`:
   ```
   .tac/config.yml
   ```

The configuration is automatically loaded when you run `tactus` commands. The `openai_api_key` value will be set as the `OPENAI_API_KEY` environment variable.

### Examples Requiring Configuration

- `simple-agent.tac` - Requires `OPENAI_API_KEY` to call the LLM
- `multi-model.tac` - Requires `OPENAI_API_KEY` to call the LLM

Examples that don't require external services (like `hello-world.tac`) work without any configuration.

## File Extension

Example files use the `.tac` extension to indicate they are Tactus procedure files written in pure Lua DSL.

## Validation

You can validate example files without running them:

```bash
tactus validate examples/hello-world.tac
```

This uses the ANTLR-generated parser to check syntax and DSL structure.

## Testing

All examples in this directory are automatically tested as part of the BDD test suite. See `features/18_example_procedures.feature` for details. Tests that require external services (like LLM calls) will be skipped if the required configuration is not available.
