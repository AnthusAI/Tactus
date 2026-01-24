# Classification Module

The `tactus.classify` module provides a comprehensive classification system with support for both LLM-based and fuzzy string matching approaches.

## Overview

All classifiers extend `BaseClassifier` and share a common interface, making them interchangeable. This enables you to switch between LLM and fuzzy matching without changing your code structure.

## When to Use

- **LLMClassifier**: Use when you need semantic understanding and context-aware classification. Ideal for ambiguous cases where the answer isn't just string matching.

- **FuzzyMatchClassifier**: Use when you're matching against known expected values with typo tolerance. Much faster than LLM calls and doesn't require API access.

## Architecture

The module uses a proper Lua class hierarchy:

- `BaseClassifier` - Abstract base with common interface
- `LLMClassifier` - LLM-powered classification with automatic retry logic
- `FuzzyMatchClassifier` - String similarity matching with configurable thresholds

All classifiers return a consistent result format:

```lua
{
    value = "Yes",           -- Classification result
    confidence = 0.85,       -- Confidence score (0.0-1.0)
    retry_count = 0,         -- Number of retries needed
    matched_text = "yes",    -- Original matched text (fuzzy only)
    raw_response = "..."     -- LLM response (LLM only)
}
```

## Loading the Module

```lua
-- Load the main module
local classify = require("tactus.classify")

-- Or load specific classifiers (dependencies auto-load)
local LLMClassifier = require("tactus.classify.llm")
local FuzzyMatchClassifier = require("tactus.classify.fuzzy")
```

## Performance Notes

- LLM classification typically takes 1-3 seconds per call
- Fuzzy matching is nearly instantaneous (<1ms)
- Consider caching LLM results for repeated classifications
- Fuzzy matching works offline and requires no API keys

## Extending Classifiers

You can extend `BaseClassifier` to create custom classifiers:

```lua
local base = require("tactus.classify.base")
local class = base.class
local BaseClassifier = base.BaseClassifier

MyClassifier = class(BaseClassifier)

function MyClassifier:init(config)
    BaseClassifier.init(self, config)
    -- Your initialization
end

function MyClassifier:classify(text)
    -- Your classification logic
    return {
        value = "Yes",
        confidence = 1.0,
        retry_count = 0
    }
end
```
