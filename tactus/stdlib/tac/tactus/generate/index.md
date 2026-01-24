# Generate Module

The `tactus.generate` module provides flexible text generation built on DSPy's modular architecture.

## Overview

All generators extend `BaseGenerator` and share a common interface. The module supports multiple output formats and optional chain-of-thought reasoning via DSPy's native modules.

## DSPy Module Integration

The generator uses DSPy's module system under the hood:

| Mode | DSPy Module | Behavior |
|------|------------|----------|
| **Default** | `Raw` | No prompt modifications - passes your system prompt and user message directly to the LLM without any DSPy formatting |
| **`reasoning = true`** | `ChainOfThought` | Uses DSPy's native reasoning module - automatically adds step-by-step thinking |

### Why Raw Mode by Default?

Even DSPy's basic `Predict` module adds formatting delimiters (like `[[ ## response ## ]]`) to prompts. The `Raw` module bypasses all DSPy prompt modifications, giving you:

- **Clean prompts**: Your system prompt goes to the LLM exactly as written
- **Predictable output**: No unexpected formatting in responses
- **Full control**: You decide what goes in the prompt

### When to Use ChainOfThought

Enable `reasoning = true` when you want the model to:
- Show its work on math problems
- Explain multi-step reasoning
- Provide transparent decision-making

The reasoning is captured separately from the final answer, so you can access both.

## Output Formats

| Format | Description |
|--------|-------------|
| `text` | Plain text output (default) |
| `json` | JSON-formatted response with validation |
| `markdown` | Markdown-formatted response |

## Architecture

The module uses a proper Lua class hierarchy:

- `BaseGenerator` - Abstract base with common interface
- `LLMGenerator` - LLM-powered generation with all options

All generators return a consistent result format:

```lua
{
    output = "The generated text...",    -- Main output (final answer)
    reasoning = "Step-by-step...",       -- Reasoning steps (only if reasoning=true)
    format = "text",                     -- Format used
    retry_count = 0,                     -- Number of retries needed
    raw_response = "...",                -- Raw LLM response
    error = nil                          -- Error message if failed
}
```

## Loading the Module

```lua
-- Load the main module
local generate = require("tactus.generate")

-- Or load specific generators (dependencies auto-load)
local LLMGenerator = require("tactus.generate.llm")
```

## Examples

### Basic Text Generation (Raw Mode)

By default, your prompt goes directly to the LLM without modification:

```lua
local generator = LLMGenerator:new {
    model = "openai/gpt-4o-mini"
}
local result = generator:generate("Write a haiku about programming")
print(result.output)
```

### Chain-of-Thought Reasoning

Enable `reasoning = true` to use DSPy's `ChainOfThought` module. The reasoning is captured in a separate field:

```lua
local generator = LLMGenerator:new {
    model = "openai/gpt-4o-mini",
    reasoning = true
}
local result = generator:generate("What is 15% of 240?")

-- Access both the reasoning and the final answer
print("Reasoning:", result.reasoning)  -- "15% means 15/100 = 0.15. So 0.15 × 240 = 36"
print("Answer:", result.output)        -- "36"
```

### JSON Output Format

```lua
local generator = LLMGenerator:new {
    model = "openai/gpt-4o-mini",
    output_format = "json"
}
local result = generator:generate("Return a JSON object with name, age, and city for a fictional person")
-- result.output will be valid JSON like: {"name": "Alice", "age": 28, "city": "Portland"}
```

### Custom System Prompt

Your system prompt is passed directly to the LLM (no DSPy modifications):

```lua
local generator = LLMGenerator:new {
    model = "openai/gpt-4o-mini",
    system_prompt = "You are a helpful coding assistant specializing in Lua.",
    temperature = 0.3
}
local result = generator:generate("How do I iterate over a table in Lua?")
```

### With Constraints

```lua
local generator = LLMGenerator:new {
    model = "openai/gpt-4o-mini",
    constraints = {"Keep response under 50 words", "Use simple language"}
}
local result = generator:generate("Explain quantum computing")
```

## Parameters Reference

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `model` | `string` | required | Model identifier (e.g., "openai/gpt-4o-mini") |
| `temperature` | `number` | 0.7 | Generation randomness (0.0-1.0) |
| `max_tokens` | `number` | nil | Maximum output tokens |
| `reasoning` | `boolean` | false | Enable ChainOfThought mode (captures reasoning separately) |
| `output_format` | `string` | "text" | Output format: "text", "json", "markdown" |
| `system_prompt` | `string` | nil | Custom system prompt (passed directly, no modifications) |
| `instructions` | `string` | nil | Additional generation instructions |
| `constraints` | `string|table` | nil | Output constraints |
| `max_retries` | `number` | 2 | Maximum retry attempts |

## Result Fields

| Field | Type | Description |
|-------|------|-------------|
| `output` | `string` | The main generated output (final answer) |
| `reasoning` | `string?` | Step-by-step reasoning (only when `reasoning = true`) |
| `format` | `string` | The output format used |
| `retry_count` | `number` | Number of retries that were needed |
| `raw_response` | `string` | The raw response from the LLM |
| `error` | `string?` | Error message if generation failed |

## Future Enhancements

Planned DSPy-inspired features:

- **Few-shot examples**: Pass examples for in-context learning
- **Optimizers**: Automatic prompt optimization with training data
- **Assertions**: Output validation with automatic retry
- **Parallel generation**: Multiple completions with selection

## Extending Generators

You can extend `BaseGenerator` to create custom generators:

```lua
local base = require("tactus.generate.base")
local class = base.class
local BaseGenerator = base.BaseGenerator

MyGenerator = class(BaseGenerator)

function MyGenerator:init(config)
    BaseGenerator.init(self, config)
    -- Your initialization
end

function MyGenerator:generate(prompt)
    -- Your generation logic
    return {
        output = "...",
        format = self.output_format,
        retry_count = 0
    }
end
```
