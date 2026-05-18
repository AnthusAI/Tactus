--[[doc
# Web Research

BDD specs for the tactus.web stdlib module.
]]

local web = require("tactus.web")

local test_state = {}

Step("I inspect web providers", function(ctx)
    test_state.result = web.providers{}
end)

Step("I run a mocked OpenAI search", function(ctx)
    test_state.result = web.search{
        provider = "openai",
        query = "automated publication systems",
        allowed_domains = {"example.com"},
        return_token_budget = "unlimited",
        mock = true,
    }
end)

Step("I run a mocked OpenAI synthesis", function(ctx)
    test_state.result = web.synthesize{
        provider = "openai",
        query = "What evidence matters for automated publication systems?",
        model = "gpt-5.4-mini",
        allowed_domains = {"example.com"},
        reasoning_effort = "low",
        mock = true,
    }
end)

Step("the web result should be ok", function(ctx)
    assert(test_state.result ~= nil, "Expected a web result")
    assert(test_state.result.ok == true, "Expected ok=true")
end)

Step("the web result should be a search result", function(ctx)
    assert(test_state.result.mode == "search",
        "Expected mode=search but got " .. tostring(test_state.result.mode))
    assert(test_state.result.results ~= nil, "Expected results")
    assert(#test_state.result.results > 0, "Expected at least one result")
    assert(test_state.result.results[1].evidence_candidate_id ~= nil,
        "Expected evidence candidate id")
end)

Step("the web result should be a synthesis result", function(ctx)
    assert(test_state.result.mode == "synthesis",
        "Expected mode=synthesis but got " .. tostring(test_state.result.mode))
    assert(test_state.result.answer ~= nil, "Expected answer")
    assert(#test_state.result.answer > 0, "Expected non-empty answer")
    assert(test_state.result.sources ~= nil, "Expected sources")
    assert(#test_state.result.sources > 0, "Expected at least one source")
end)

Step("the providers should include OpenAI and reserved future providers", function(ctx)
    local providers = test_state.result.providers
    assert(providers ~= nil, "Expected providers")
    assert(providers.openai ~= nil, "Expected OpenAI provider")
    assert(providers.perplexity ~= nil, "Expected planned Perplexity provider")
    assert(providers.gemini ~= nil, "Expected reserved Gemini provider")
end)

Specification([[
Feature: Web Research
  As a Tactus developer
  I want reusable web research primitives
  So that host applications can expose web evidence without custom adapters

  Scenario: Inspect available providers
    When I inspect web providers
    Then the web result should be ok
    And the providers should include OpenAI and reserved future providers

  Scenario: Mocked web search
    When I run a mocked OpenAI search
    Then the web result should be ok
    And the web result should be a search result

  Scenario: Mocked synthesis
    When I run a mocked OpenAI synthesis
    Then the web result should be ok
    And the web result should be a synthesis result
]])

Procedure {
    output = {
        result = field.string{required = true}
    },
    function(input)
        return {result = "Web stdlib specs executed"}
    end
}
