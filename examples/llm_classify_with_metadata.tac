-- LLM Classification with Metadata Interpolation Example
-- Demonstrates using dynamic prompts with captured values

-- Define custom steps with regex patterns
Step("a classifier asking if \"(.+)\" is blue", function(ctx, item)
    local prompt_text = string.format([[
Item: %s

Question: Is this item BLUE?
Answer ONLY with Yes or No.
]], item)

    ctx.classifier = Classify {
        method = "llm",
        classes = {"Yes", "No"},
        prompt = prompt_text,
        name = "llm_metadata_classifier",
        model = "openai/gpt-4o-mini",
        temperature = 0,
        max_retries = 3
    }
    ctx.item = item
end)

Step("I classify the item", function(ctx)
    ctx.result = ctx.classifier(ctx.item)
end)

Step("the answer should be \"(.+)\"", function(ctx, expected)
    assert(ctx.result.value == expected,
        "Expected '" .. expected .. "' but got '" .. ctx.result.value .. "'")
end)

Mocks {
    llm_metadata_classifier = {
        message = "Yes\nMocked classification.",
        temporal = {
            {
                when_message = [[Please classify the following:

blue widget]],
                message = "Yes\nThe item is explicitly blue."
            },
            {
                when_message = [[Please classify the following:

red gadget]],
                message = "No\nThe item is red, not blue."
            },
            {
                when_message = [[Please classify the following:

azure sky painting]],
                message = "Yes\nAzure is a shade of blue."
            },
            {
                when_message = [[Please classify the following:

green plant]],
                message = "No\nThe item is green, not blue."
            }
        }
    }
}

-- BDD Specification
Specification([[
Feature: LLM Classification with Metadata Interpolation
  As a developer using Tactus
  I want to interpolate values into classifier prompts
  So that I can make dynamic classification decisions

  Scenario: Blue widget is identified as blue
    Given a classifier asking if "blue widget" is blue
    When I classify the item
    Then the answer should be "Yes"

  Scenario: Red gadget is not identified as blue
    Given a classifier asking if "red gadget" is blue
    When I classify the item
    Then the answer should be "No"

  Scenario: Azure sky painting is identified as blue
    Given a classifier asking if "azure sky painting" is blue
    When I classify the item
    Then the answer should be "Yes"

  Scenario: Green plant is not identified as blue
    Given a classifier asking if "green plant" is blue
    When I classify the item
    Then the answer should be "No"
]])

-- Minimal procedure to satisfy framework requirement
Procedure {
    output = {
        result = field.string{required = true}
    },
    function(input)
        return {result = "Tests executed via BDD specification"}
    end
}
