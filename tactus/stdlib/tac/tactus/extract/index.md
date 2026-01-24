# Extraction Module

The `tactus.extract` module provides structured data extraction from unstructured text using LLM-based analysis.

## Overview

All extractors extend `BaseExtractor` and share a common interface. This enables consistent usage patterns and makes it easy to add new extraction strategies in the future.

## When to Use

- **LLMExtractor**: Use when you need to extract structured fields from natural language text. Ideal for forms, documents, conversations, and any unstructured data where field values aren't in a predictable format.

## Architecture

The module uses a proper Lua class hierarchy:

- `BaseExtractor` - Abstract base with common interface and field validation
- `LLMExtractor` - LLM-powered extraction with automatic retry logic

All extractors return a consistent result format:

```lua
{
    fields = {              -- Extracted field values
        name = "John Smith",
        age = 34,
        email = "john@example.com"
    },
    retry_count = 0,        -- Number of retries needed
    raw_response = "...",   -- LLM response (LLM only)
    error = nil,            -- Error message if failed
    validation_errors = {}  -- List of validation errors
}
```

## Loading the Module

```lua
-- Load the main module
local extract = require("tactus.extract")

-- Or load specific extractors (dependencies auto-load)
local LLMExtractor = require("tactus.extract.llm")
```

## Field Types

LLMExtractor supports these field types for validation:

| Type | Description | Example |
|------|-------------|---------|
| `string` | Text values | `"John Smith"` |
| `number` | Numeric values (float) | `34.5` |
| `integer` | Whole numbers | `34` |
| `boolean` | True/false values | `true` |
| `list`/`array` | JSON arrays | `["a", "b", "c"]` |
| `object`/`dict` | JSON objects | `{key = "value"}` |

## Performance Notes

- LLM extraction typically takes 1-3 seconds per call
- Retry logic adds latency for malformed responses
- Consider caching extraction results for repeated operations
- Use the `strict` parameter to control validation behavior

## Extending Extractors

You can extend `BaseExtractor` to create custom extractors:

```lua
local base = require("tactus.extract.base")
local class = base.class
local BaseExtractor = base.BaseExtractor

MyExtractor = class(BaseExtractor)

function MyExtractor:init(config)
    BaseExtractor.init(self, config)
    -- Your initialization
end

function MyExtractor:extract(text)
    -- Your extraction logic
    local fields = {}
    -- ... populate fields ...

    -- Validate against schema
    local validated, errors = self:validate_fields(fields, self.fields)

    return {
        fields = validated,
        validation_errors = errors,
        retry_count = 0
    }
end
```
