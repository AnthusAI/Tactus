--[[doc
# Deepgram Utilities

BDD specs for the tactus.deepgram stdlib module.
]]

local deepgram = require("tactus.deepgram")
local json = require("tactus.io.json")

local test_state = {}

local fixtures = {
    spacewalk_trimmed = [=[{"metadata":{"channels":1,"created":"2024-02-12T18:27:21.342Z"},"results":{"channels":[{"alternatives":[{"transcript":"Yeah. As as much as, it's worth celebrating, the first, spacewalk, with","words":[{"word":"yeah","start":0.08,"end":0.32,"confidence":0.9975586,"punctuated_word":"Yeah.","speaker":0,"speaker_confidence":0.0,"sentiment":"","sentiment_score":0.0},{"word":"as","start":0.32,"end":0.79999995,"confidence":0.9921875,"punctuated_word":"As","speaker":0,"speaker_confidence":0.0,"sentiment":"","sentiment_score":0.0},{"word":"as","start":0.79999995,"end":1.04,"confidence":0.96777344,"punctuated_word":"as","speaker":0,"speaker_confidence":0.0,"sentiment":"","sentiment_score":0.0},{"word":"much","start":1.04,"end":1.28,"confidence":1.0,"punctuated_word":"much","speaker":0,"speaker_confidence":0.0,"sentiment":"","sentiment_score":0.0},{"word":"as","start":1.28,"end":1.5999999,"confidence":0.9926758,"punctuated_word":"as,","speaker":0,"speaker_confidence":0.0,"sentiment":"","sentiment_score":0.0},{"word":"it's","start":2.0,"end":2.24,"confidence":1.0,"punctuated_word":"it's","speaker":0,"speaker_confidence":0.0,"sentiment":"","sentiment_score":0.0},{"word":"worth","start":2.24,"end":2.74,"confidence":1.0,"punctuated_word":"worth","speaker":0,"speaker_confidence":0.0,"sentiment":"","sentiment_score":0.0},{"word":"celebrating","start":2.8,"end":3.3,"confidence":0.97143555,"punctuated_word":"celebrating,","speaker":0,"speaker_confidence":0.0,"sentiment":"","sentiment_score":0.0},{"word":"the","start":4.4,"end":4.64,"confidence":0.9980469,"punctuated_word":"the","speaker":0,"speaker_confidence":0.0,"sentiment":"","sentiment_score":0.0},{"word":"first","start":4.64,"end":5.04,"confidence":0.8017578,"punctuated_word":"first,","speaker":0,"speaker_confidence":0.0,"sentiment":"","sentiment_score":0.0},{"word":"spacewalk","start":5.2799997,"end":5.7799997,"confidence":0.9468994,"punctuated_word":"spacewalk,","speaker":0,"speaker_confidence":0.0,"sentiment":"","sentiment_score":0.0},{"word":"with","start":6.3199997,"end":6.56,"confidence":1.0,"punctuated_word":"with","speaker":0,"speaker_confidence":0.0,"sentiment":"","sentiment_score":0.0}]}]}]}}]=],
    paragraphs_sample = [=[{"results":{"channels":[{"alternatives":[{"transcript":"Hello world. Second sentence.","paragraphs":{"transcript":"Hello world. Second sentence.","paragraphs":[{"sentences":[{"text":"Hello world.","start":0.0,"end":0.9},{"text":"Second sentence.","start":1.0,"end":1.9}]}]},"words":[{"word":"Hello","punctuated_word":"Hello","start":0.0,"end":0.4,"speaker":1},{"word":"world","punctuated_word":"world.","start":0.4,"end":0.9,"speaker":1},{"word":"Second","punctuated_word":"Second","start":1.0,"end":1.4,"speaker":2},{"word":"sentence","punctuated_word":"sentence.","start":1.4,"end":1.9,"speaker":2}]}]}]}}]=],
    utterances_sample = [=[{"results":{"utterances":[{"transcript":"Hi there.","start":0.0,"end":1.0,"speaker":1,"channel":0,"words":[{"word":"Hi","punctuated_word":"Hi","start":0.0,"end":0.4,"speaker":1},{"word":"there","punctuated_word":"there.","start":0.4,"end":1.0,"speaker":1}]},{"transcript":"General Kenobi.","start":1.2,"end":2.0,"speaker":2,"channel":0,"words":[{"word":"General","punctuated_word":"General","start":1.2,"end":1.6,"speaker":2},{"word":"Kenobi","punctuated_word":"Kenobi.","start":1.6,"end":2.0,"speaker":2}]}],"channels":[{"alternatives":[{"transcript":"Hi there. General Kenobi.","words":[{"word":"Hi","punctuated_word":"Hi","start":0.0,"end":0.4,"speaker":1},{"word":"there","punctuated_word":"there.","start":0.4,"end":1.0,"speaker":1},{"word":"General","punctuated_word":"General","start":1.2,"end":1.6,"speaker":2},{"word":"Kenobi","punctuated_word":"Kenobi.","start":1.6,"end":2.0,"speaker":2}]}]}]}}]=],
    multichannel_sample = [=[{"results":{"channels":[{"alternatives":[{"words":[{"word":"hi","punctuated_word":"hi","start":0.0,"end":0.2,"speaker":1},{"word":"there","punctuated_word":"there","start":1.0,"end":1.2,"speaker":1}]}]},{"alternatives":[{"words":[{"word":"hello","punctuated_word":"hello","start":0.5,"end":0.7,"speaker":2},{"word":"friend","punctuated_word":"friend","start":1.5,"end":1.7,"speaker":2}]}]}]}}]=],
}

local function load_fixture(name)
    local raw = fixtures[name]
    assert(raw ~= nil, "Unknown fixture: " .. tostring(name))
    return json.decode(raw)
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
    expected = string.gsub(expected, "\\n", "\n")
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
    When I extract words text without speakers
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
