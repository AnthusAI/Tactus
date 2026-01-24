--[[doc
# Extraction Classes

Proper Lua class hierarchy for structured data extraction:

- **BaseExtractor**: Abstract base class with field validation
- **LLMExtractor**: LLM-based extraction with retry logic

## Usage

```lua
-- Import extraction classes
local extract = require("tactus.extract")
local LLMExtractor = extract.LLMExtractor

-- Or load specific extractors (dependencies auto-load):
local LLMExtractor = require("tactus.extract.llm")

-- LLM Extraction
local extractor = LLMExtractor:new {
    fields = {name = "string", age = "number", email = "string"},
    prompt = "Extract customer information from this text",
    model = "openai/gpt-4o-mini"
}
local result = extractor:extract("John Smith is 34 years old. Contact: john@example.com")
-- result.fields = {name = "John Smith", age = 34, email = "john@example.com"}
```

## LLMExtractor Parameters

- `fields` (required): Table mapping field names to types
- `prompt` (required): Extraction instruction
- `model`: Model identifier (e.g., "openai/gpt-4o-mini")
- `temperature`: LLM temperature (default: 0.3)
- `max_retries`: Maximum retry attempts (default: 3)
- `strict`: Require all fields (default: true)

## Field Types

- `string`: Text values
- `number`: Numeric values (float)
- `integer`: Whole numbers
- `boolean`: true/false values
- `list`/`array`: JSON arrays
- `object`/`dict`: JSON objects
]]

-- Load extraction classes
local extract = require("tactus.extract")
local LLMExtractor = extract.LLMExtractor

-- Local state for test context
local test_state = {}

-- Custom step definitions
Step("an LLM extractor with fields (.+)", function(ctx, fields_str)
    local fields = {}
    -- Parse field definitions like: name:string, age:number
    for field_def in string.gmatch(fields_str, "([^,]+)") do
        field_def = field_def:gsub("^%s+", ""):gsub("%s+$", "")
        local name, type_ = field_def:match("([^:]+):([^:]+)")
        if name and type_ then
            fields[name:gsub("^%s+", ""):gsub("%s+$", "")] = type_:gsub("^%s+", ""):gsub("%s+$", "")
        end
    end
    test_state.extractor_config = {
        fields = fields,
        model = "openai/gpt-4o-mini"
    }
end)

Step("extraction prompt \"(.+)\"", function(ctx, prompt)
    test_state.extractor_config.prompt = prompt
end)

Step("I extract from \"(.+)\"", function(ctx, text)
    if not test_state.extractor then
        test_state.extractor = LLMExtractor:new(test_state.extractor_config)
    end
    test_state.result = test_state.extractor:extract(text)
end)

Step("the extracted field \"(.+)\" should be \"(.+)\"", function(ctx, field, expected)
    assert(test_state.result, "No extraction result found")
    assert(test_state.result.fields, "No fields in extraction result")
    local actual = test_state.result.fields[field]
    assert(tostring(actual) == expected,
        "Expected field '" .. field .. "' to be '" .. expected .. "' but got '" .. tostring(actual) .. "'")
end)

Step("the extracted field \"(.+)\" should be number (.+)", function(ctx, field, expected)
    assert(test_state.result, "No extraction result found")
    assert(test_state.result.fields, "No fields in extraction result")
    local actual = test_state.result.fields[field]
    assert(type(actual) == "number",
        "Expected field '" .. field .. "' to be a number but got " .. type(actual))
    assert(actual == tonumber(expected),
        "Expected field '" .. field .. "' to be " .. expected .. " but got " .. tostring(actual))
end)

Step("the extraction should succeed", function(ctx)
    assert(test_state.result, "No extraction result found")
    assert(not test_state.result.error,
        "Extraction failed with error: " .. tostring(test_state.result.error))
end)

Step("the extraction should have no validation errors", function(ctx)
    assert(test_state.result, "No extraction result found")
    local errors = test_state.result.validation_errors or {}
    assert(#errors == 0,
        "Expected no validation errors but got: " .. table.concat(errors, ", "))
end)

-- BDD Specifications
Specification([[
Feature: Extraction Class Hierarchy
  As a Tactus developer
  I want to extract structured data from text
  So that I can process unstructured information programmatically

  Scenario: Extract simple contact information
    Given an LLM extractor with fields name:string, age:number
    And extraction prompt "Extract the person's name and age"
    When I extract from "John Smith is 34 years old"
    Then the extraction should succeed
    And the extracted field "name" should be "John Smith"
    And the extracted field "age" should be number 34

  Scenario: Extract multiple string fields
    Given an LLM extractor with fields city:string, country:string
    And extraction prompt "Extract the city and country"
    When I extract from "The meeting will be held in Paris, France"
    Then the extraction should succeed
    And the extracted field "city" should be "Paris"
    And the extracted field "country" should be "France"

  Scenario: Extract with validation
    Given an LLM extractor with fields product:string, price:number, quantity:integer
    And extraction prompt "Extract product details"
    When I extract from "Order: 5 widgets at $19.99 each"
    Then the extraction should succeed
    And the extraction should have no validation errors
]])

-- Minimal procedure
Procedure {
    output = {
        result = field.string{required = true}
    },
    function(input)
        return {result = "Extraction class hierarchy specs executed"}
    end
}
