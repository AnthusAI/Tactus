--[[doc
# biblicus.text

Biblicus-powered text utilities for Tactus.

This module exposes Biblicus text helpers through the Tactus stdlib. It mirrors
the Biblicus request/response shapes while keeping configuration in Tactus.

## Usage

```lua
local text = require("biblicus.text")

local result = text.extract({
    text = "Alice met Bob in Paris.",
    client = {
        provider = "openai",
        model = "gpt-4o-mini"
    },
    prompt_template = "Extract the person names in the text.",
})
```

## Testing hook

For deterministic tests, use Tactus `Mocks {}` to return stable Biblicus
results without touching the model.
]]

local text = require("tactus.biblicus.text")

return text
