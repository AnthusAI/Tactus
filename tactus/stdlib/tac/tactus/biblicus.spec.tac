--[[doc
# Biblicus Text Utilities

This specification covers the Biblicus-backed `biblicus.text` stdlib module.
It exercises the deterministic mock path plus markup helper functions.
]]

local text = require("biblicus.text")

local test_state = {}
local function build_request(text_value)
    local client = {
        provider = "openai",
        model = "gpt-4o-mini"
    }
    return {
        text = text_value,
        client = client,
        prompt_template = "Return only the updated markup."
    }
end

Step("a biblicus request for \"(.+)\"", function(ctx, raw_text)
    test_state.request = build_request(raw_text)
end)

Step("I apply mock extraction markup \"(.+)\"", function(ctx, markup)
    local request = test_state.request
    request.mock_marked_up_text = markup
    local ok, result = pcall(text.extract, request)
    assert(ok, "text.extract failed: " .. tostring(result))
    test_state.result = result
end)

Step("the extracted span should be \"(.+)\"", function(ctx, expected)
    local spans = test_state.result.spans or {}
    assert(#spans == 1, "Expected one span")
    assert(spans[1].text == expected,
        "Expected span text '" .. expected .. "' but got '" .. tostring(spans[1].text) .. "'")
end)

Step("I apply mock annotation markup \"(.+)\"", function(ctx, markup)
    local request = test_state.request
    request.mock_marked_up_text = markup
    local ok, result = pcall(text.annotate, request)
    assert(ok, "text.annotate failed: " .. tostring(result))
    test_state.result = result
end)

Step("the annotation span label should be \"(.+)\"", function(ctx, expected)
    local spans = test_state.result.spans or {}
    assert(#spans == 1, "Expected one span")
    assert(spans[1].attributes.label == expected,
        "Expected label '" .. expected .. "' but got '" .. tostring(spans[1].attributes.label) .. "'")
end)

Step("I apply mock link markup \"(.+)\"", function(ctx, markup)
    local request = test_state.request
    request.mock_marked_up_text = markup
    request.id_prefix = "link_"
    local ok, result = pcall(text.link, request)
    assert(ok, "text.link failed: " .. tostring(result))
    test_state.result = result
end)

Step("the link spans should include ids", function(ctx)
    local spans = test_state.result.spans or {}
    assert(#spans == 2, "Expected two spans")
    assert(spans[1].attributes.id == "link_1", "Expected first span id link_1")
    assert(spans[2].attributes.ref == "link_1", "Expected second span ref link_1")
end)

Step("I apply mock redaction markup \"(.+)\"", function(ctx, markup)
    local request = test_state.request
    request.mock_marked_up_text = markup
    local ok, result = pcall(text.redact, request)
    assert(ok, "text.redact failed: " .. tostring(result))
    test_state.result = result
end)

Step("the redaction should return one span", function(ctx)
    local spans = test_state.result.spans or {}
    assert(#spans == 1, "Expected one redaction span")
end)

Step("I apply mock slice markup \"(.+)\"", function(ctx, markup)
    local request = test_state.request
    request.mock_marked_up_text = markup
    local ok, result = pcall(text.slice, request)
    assert(ok, "text.slice failed: " .. tostring(result))
    test_state.result = result
end)

Step("the slices should be \"(.+)\" and \"(.+)\"", function(ctx, first, second)
    local slices = test_state.result.slices or {}
    assert(#slices == 2, "Expected two slices")
    assert(slices[1].text == first, "Expected first slice '" .. first .. "'")
    assert(slices[2].text == second, "Expected second slice '" .. second .. "'")
end)

Step("I strip span tags from \"(.+)\"", function(ctx, markup)
    test_state.cleaned = text.strip_span_tags(markup)
end)

Step("the stripped text should be \"(.+)\"", function(ctx, expected)
    assert(test_state.cleaned == expected,
        "Expected stripped text '" .. expected .. "' but got '" .. tostring(test_state.cleaned) .. "'")
end)

Step("I parse spans from \"(.+)\"", function(ctx, markup)
    test_state.parsed_spans = text.parse_span_markup(markup)
end)

Step("the parsed span text should be \"(.+)\"", function(ctx, expected)
    local spans = test_state.parsed_spans or {}
    assert(#spans == 1, "Expected one parsed span")
    assert(spans[1].text == expected,
        "Expected span text '" .. expected .. "' but got '" .. tostring(spans[1].text) .. "'")
end)

Step("I summarize span 1 from \"(.+)\"", function(ctx, markup)
    local summaries = text.summarize_span_context(markup, {1})
    test_state.summary = summaries[1]
end)

Step("the summary should be \"(.+)\"", function(ctx, expected)
    assert(test_state.summary == expected,
        "Expected summary '" .. expected .. "' but got '" .. tostring(test_state.summary) .. "'")
end)

Specification([[
Feature: Biblicus Text Utilities
  As a Tactus developer
  I want to access Biblicus text utilities from the stdlib
  So that I can reuse Biblicus text processing in workflows

  Scenario: Extract spans from mock markup
    Given a biblicus request for "Alice met Bob."
    When I apply mock extraction markup "Alice met <span>Bob</span>."
    Then the extracted span should be "Bob"

  Scenario: Annotate spans with attributes
    Given a biblicus request for "Ada wrote code."
    When I apply mock annotation markup "Ada wrote <span label=\"artifact\">code</span>."
    Then the annotation span label should be "artifact"

  Scenario: Link repeated spans
    Given a biblicus request for "Alice met Bob and Bob waved."
    When I apply mock link markup "Alice met <span id=\"link_1\">Bob</span> and <span ref=\"link_1\">Bob</span> waved."
    Then the link spans should include ids

  Scenario: Redact spans without types
    Given a biblicus request for "The secret is safe."
    When I apply mock redaction markup "The <span>secret</span> is safe."
    Then the redaction should return one span

  Scenario: Slice text into segments
    Given a biblicus request for "First sentence. Second sentence."
    When I apply mock slice markup "First sentence.<slice/> Second sentence."
    Then the slices should be "First sentence." and " Second sentence."

  Scenario: Use markup helpers
    Given a biblicus request for "Ignored."
    When I strip span tags from "Hello <span>world</span>."
    Then the stripped text should be "Hello world."
    When I parse spans from "Hello <span>world</span>."
    Then the parsed span text should be "world"
    When I summarize span 1 from "Hello <span>world</span>."
    Then the summary should be "Span 1: world"
]])

Procedure {
    output = {
        result = field.string{required = true}
    },
    function(input)
        return {result = "Biblicus text stdlib specs executed"}
    end
}
