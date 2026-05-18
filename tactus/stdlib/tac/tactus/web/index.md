# Web Research

`tactus.web` provides reusable web research primitives for agents and host
applications. The active first provider is OpenAI Responses `web_search`.

```lua
local web = require("tactus.web")

local results = web.search{
    provider = "openai",
    query = "automated publication systems newsroom architecture",
    model = "gpt-5.4-mini",
    allowed_domains = {"openai.com"},
    return_token_budget = "unlimited", -- or "default"
}

local synthesis = web.synthesize{
    provider = "openai",
    query = "Summarize recent evidence about automated publication QA systems.",
    model = "gpt-5.4-mini",
    allowed_domains = {"openai.com"},
    reasoning_effort = "low",
}
```

## Providers

- `openai` supports `web.search{...}` and `web.synthesize{...}` through the
  OpenAI Responses API `web_search` tool and requires `OPENAI_API_KEY`.
- `perplexity` is reserved for a future raw Search API provider milestone.
- `gemini` Deep Research APIs are reserved but intentionally not implemented in
  this milestone because that capability is async/background-oriented.

`web.providers{}` returns provider capabilities and whether the relevant
environment key is present.

## Output Contracts

`web.search{...}` returns:

```lua
{
    ok = true,
    provider = "openai",
    mode = "search",
    query = "...",
    results = {
        {
            title = "...",
            url = "...",
            snippet = "...",
            date = "...",
            last_updated = "...",
            rank = 1,
            source_domain = "...",
            evidence_candidate_id = "...",
        }
    },
    metadata = {...},
}
```

`web.synthesize{...}` returns:

```lua
{
    ok = true,
    provider = "openai",
    mode = "synthesis",
    query = "...",
    answer = "...",
    sources = {...},
    metadata = {...},
}
```

Provider selection is explicit. Tactus does not silently fall back from one
provider to another.
