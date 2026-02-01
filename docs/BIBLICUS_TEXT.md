# Biblicus Text Utilities

The `biblicus.text` standard library module exposes Biblicus text utilities inside
Tactus. It mirrors Biblicus request/response shapes while letting you configure
providers and models using Tactus conventions.

## Module Path

```lua
local text = require("biblicus.text")
```

## Configuration

Each operation accepts a `client` table that mirrors Biblicus `LlmClientConfig`:

```lua
client = {
    provider = "openai",
    model = "gpt-4o-mini",
    api_key = "optional",
    api_base = "optional",
    temperature = 0.2,
    max_tokens = 512,
    response_format = "text",
    max_retries = 1,
    timeout_seconds = 30,
    model_type = "optional",
    extra_params = {
        -- provider-specific values
    }
}
```

If you pass a full LiteLLM model string (e.g. `openai/gpt-4o-mini`) you may omit
`provider`.

## Text Operations

Each operation accepts:

- `text`: The input string to process.
- `client`: The LLM configuration table.
- `prompt_template`: A user prompt that must not include `{text}`.
- `max_rounds` and `max_edits_per_round` are optional.

Biblicus handles the internal markup protocol for span/slice edits. Most callers
only need to provide the user instruction in `prompt_template`.

### Extract

```lua
local result = text.extract({
    text = "Alice met Bob in Paris.",
    client = { provider = "openai", model = "gpt-4o-mini" },
    prompt_template = "Extract the person names in the text.",
})
```

### Annotate

```lua
local result = text.annotate({
    text = "Ada wrote code.",
    client = { provider = "openai", model = "gpt-4o-mini" },
    prompt_template = "Label the word code as artifact.",
    allowed_attributes = {"label"}
})
```

### Link

```lua
local result = text.link({
    text = "Alice met Bob and Bob waved.",
    client = { provider = "openai", model = "gpt-4o-mini" },
    prompt_template = "Link repeated names to their first mention.",
    id_prefix = "link_"
})
```

### Redact

```lua
local result = text.redact({
    text = "The secret is safe.",
    client = { provider = "openai", model = "gpt-4o-mini" },
    prompt_template = "Redact the word secret.",
    redaction_types = nil
})
```

### Slice

```lua
local result = text.slice({
    text = "First sentence. Second sentence.",
    client = { provider = "openai", model = "gpt-4o-mini" },
    prompt_template = "Split the text into two slices at the sentence boundary.",
})
```

## Markup Helpers

```lua
local cleaned = text.strip_span_tags("Hello <span>world</span>.")
local spans = text.parse_span_markup("Hello <span>world</span>.")
local summaries = text.summarize_span_context("Hello <span>world</span>.", {1})
```

## Deterministic Testing

For deterministic tests (BDD specs, CI), use Tactus `Mocks {}` to return
stable Biblicus results without touching the model:

```lua
Mocks {
    ["biblicus.text.extract"] = {
        returns = {
            marked_up_text = "<span>Alice</span> met <span>Bob</span>.",
            spans = {
                {index = 1, start_char = 0, end_char = 5, text = "Alice"},
                {index = 2, start_char = 10, end_char = 13, text = "Bob"}
            },
            warnings = {}
        }
    }
}
```

This is a testing hook and should not be used for production workflows.
