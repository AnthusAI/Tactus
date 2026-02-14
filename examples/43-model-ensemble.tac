-- Example: Ensemble vote across multiple model backends
-- Demonstrates: type="ensemble" and the canonical model call/unwrapping pattern.

Model "sentiment_ensemble" {
  type = "ensemble",
  strategy = "vote",
  members = {
    { type = "mock", value = "positive" },
    { type = "mock", value = "negative" },
    { type = "mock", value = "positive" },
  },
  input = { text = "string" },
  output = { label = "string" }
}

Procedure {
  input = { text = field.string{required = true} },
  output = { label = field.string{required = true} },
  function(input)
    local ensemble = Model("sentiment_ensemble")
    local result = ensemble({text = input.text})
    local out = result.output or result
    return { label = out }
  end
}

Specification([[
Feature: Ensemble Model
  Scenario: Majority vote returns the winning label
    Given the procedure has started
    And the input text is "Any text works here."
    When the procedure runs
    Then the output label should be "positive"
    And the procedure should complete successfully
]])
