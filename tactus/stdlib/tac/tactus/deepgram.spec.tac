--[[doc
# Deepgram Utilities

BDD specs for the tactus.deepgram stdlib module.
]]

local deepgram = require("tactus.deepgram")
local json = require("tactus.io.json")

local test_state = {}

local function load_fixture(name)
    local path = "tests/fixtures/deepgram/" .. name .. ".json"
    return json.read(path)
end

Step("a deepgram fixture \"(.+)\"", function(ctx, name)
    test_state.data = load_fixture(name)
end)

Step("I extract words text", function(ctx)
    test_state.text = deepgram.words_text(test_state.data)
end)

Step("I extract words text without speakers", function(ctx)
    test_state.text = deepgram.words_text(test_state.data, {include_speakers = false})
end)

Step("I extract sentences text", function(ctx)
    test_state.text = deepgram.sentences_text(test_state.data)
end)

Step("I extract paragraphs text", function(ctx)
    test_state.text = deepgram.paragraphs_text(test_state.data)
end)

Step("I extract utterances text", function(ctx)
    test_state.text = deepgram.utterances_text(test_state.data)
end)

Step("I extract auto text without speakers", function(ctx)
    test_state.text = deepgram.text(test_state.data, {
        source = "auto",
        include_speakers = false,
        separator = "|",
    })
end)

Step("the text should be \"(.+)\"", function(ctx, expected)
    assert(test_state.text == expected,
        "Expected text '" .. expected .. "' but got '" .. tostring(test_state.text) .. "'")
end)

Step("I fuzzy match quote \"(.+)\"", function(ctx, quote)
    test_state.quote = deepgram.quote(test_state.data, {
        quote = quote,
        method = "fuzzy",
    })
end)

Step("I LLM match quote \"(.+)\" with markup \"(.+)\"", function(ctx, quote, markup)
    test_state.quote = deepgram.quote(test_state.data, {
        quote = quote,
        method = "llm",
        client = {provider = "openai", model = "gpt-4o-mini"},
        mock_marked_up_text = markup,
    })
end)

Step("the quote should be \"(.+)\" with start (.+) and end (.+) and speaker (.+) via \"(.+)\"", function(ctx, text, start_time, end_time, speaker, method)
    local quote = test_state.quote
    assert(quote, "Expected quote result")
    assert(quote.text == text, "Expected quote text '" .. text .. "' but got '" .. tostring(quote.text) .. "'")
    assert(quote.start == tonumber(start_time), "Expected start " .. start_time .. " but got " .. tostring(quote.start))
    assert(quote["end"] == tonumber(end_time), "Expected end " .. end_time .. " but got " .. tostring(quote["end"]))
    assert(quote.speaker == tonumber(speaker), "Expected speaker " .. speaker .. " but got " .. tostring(quote.speaker))
    assert(quote.method == method, "Expected method '" .. method .. "' but got '" .. tostring(quote.method) .. "'")
end)

Specification([[
Feature: Deepgram Utilities
  As a Tactus developer
  I want to flatten Deepgram JSON and extract quotes with timestamps
  So that I can reuse transcript processing in workflows

  Scenario: Words text uses punctuated words
    Given a deepgram fixture "spacewalk_trimmed"
    When I extract words text
    Then the text should be "Yeah. As as much as, it's worth celebrating, the first, spacewalk, with"

  Scenario: Sentences text uses paragraph sentences with speaker prefixes
    Given a deepgram fixture "paragraphs_sample"
    When I extract sentences text
    Then the text should be "Speaker 1: Hello world.\nSpeaker 2: Second sentence."

  Scenario: Paragraphs text uses paragraph transcript
    Given a deepgram fixture "paragraphs_sample"
    When I extract paragraphs text
    Then the text should be "Hello world. Second sentence."

  Scenario: Utterances text includes speakers
    Given a deepgram fixture "utterances_sample"
    When I extract utterances text
    Then the text should be "Speaker 1: Hi there.\nSpeaker 2: General Kenobi."

  Scenario: Auto text falls back to sentences
    Given a deepgram fixture "paragraphs_sample"
    When I extract auto text without speakers
    Then the text should be "Hello world.|Second sentence."

  Scenario: Multi-channel words are time ordered
    Given a deepgram fixture "multichannel_sample"
    When I extract words text without speakers
    Then the text should be "hi hello there friend"

  Scenario: Fuzzy quote matching returns timestamps
    Given a deepgram fixture "utterances_sample"
    When I fuzzy match quote "General Kenobi"
    Then the quote should be "General Kenobi." with start 1.2 and end 2.0 and speaker 2 via "fuzzy"

  Scenario: LLM quote matching aligns span to timestamps
    Given a deepgram fixture "utterances_sample"
    When I LLM match quote "Hi there" with markup "<span>Hi there</span>."
    Then the quote should be "Hi there." with start 0.0 and end 1.0 and speaker 1 via "llm"
]])

Procedure {
    output = {
        result = field.string{required = true}
    },
    function(input)
        return {result = "Deepgram stdlib specs executed"}
    end
}
