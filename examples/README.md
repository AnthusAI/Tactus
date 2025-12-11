# Tactus Examples

This directory contains example Tactus procedure files that demonstrate how to use the Tactus DSL.

## Running Examples

Each example can be run directly with the Tactus CLI:

```bash
tactus run examples/hello-world.tyml
tactus run examples/with-parameters.tyml --param task="My task" --param count=10
```

## Example Files

### hello-world.tyml

A basic "Hello World" example that demonstrates:
- Simple workflow execution
- State management with State primitive
- Logging operations
- Output schema validation

**Run:**
```bash
tactus run examples/hello-world.tyml
```

### state-management.tyml

Demonstrates state operations:
- Setting and getting state values
- Incrementing numeric state
- Iterating with state tracking
- Returning structured output

**Run:**
```bash
tactus run examples/state-management.tyml
```

### with-parameters.tyml

Shows how to use parameters:
- Declaring parameters with types and defaults
- Accessing parameters in workflow code
- Overriding parameters via CLI

**Run:**
```bash
# Use defaults
tactus run examples/with-parameters.tyml

# Override parameters
tactus run examples/with-parameters.tyml --param task="Custom task" --param count=5
```

## Configuration

Some examples require configuration, particularly LLM-based examples that need an OpenAI API key.

### Setting Up Configuration

1. Create a `.tactus` directory in your project root:
   ```bash
   mkdir -p .tactus
   ```

2. Copy the example config file:
   ```bash
   cp examples/.tactus/config.yml.example .tactus/config.yml
   ```

3. Edit `.tactus/config.yml` and add your OpenAI API key:
   ```yaml
   openai_api_key: "sk-your-actual-api-key-here"
   ```

4. Add `.tactus/config.yml` to your `.gitignore`:
   ```
   .tactus/config.yml
   ```

The configuration is automatically loaded when you run `tactus` commands. The `openai_api_key` value will be set as the `OPENAI_API_KEY` environment variable.

### Examples Requiring Configuration

- `simple-agent.tyml` - Requires `OPENAI_API_KEY` to call the LLM

Examples that don't require external services (like `hello-world.tyml`) work without any configuration.

## File Extension

Example files use the `.tyml` extension to indicate they are Tactus procedure files. This helps distinguish them from generic YAML files while maintaining YAML syntax compatibility.

## Testing

All examples in this directory are automatically tested as part of the integration test suite. See `tests/integration/test_examples.py` for details. Tests that require external services (like LLM calls) will be skipped if the required configuration is not available.
