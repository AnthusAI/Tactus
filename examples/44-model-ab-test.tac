-- Example: A/B routing between two candidates
-- Demonstrates: type="ab_test" and reading the chosen arm from PredictionResult.metadata.

Model "ab_classifier" {
  type = "ab_test",
  -- Force deterministic behavior for the example/spec.
  seed = 123,
  weights = {0.0, 1.0},
  arms = {
    { type = "mock", value = "A" },
    { type = "mock", value = "B" },
  },
  input = { text = "string" },
  output = { label = "string" }
}

Procedure {
  input = { text = field.string{required = true} },
  output = { label = field.string{required = true}, arm = field.number{required = true} },
  function(input)
    local router = Model("ab_classifier")
    local result = router({text = input.text})
    local out = result.output or result

    local arm_index = nil
    local meta = result.metadata or result.meta
    if meta then
      pcall(function() arm_index = meta.arm_index end)
      if arm_index == nil then
        pcall(function() arm_index = meta["arm_index"] end)
      end
    end

    return {
      label = out,
      arm = arm_index or -1
    }
  end
}

Specification([[
Feature: AB Test Model
  Scenario: Deterministic routing selects arm 1
    Given the procedure has started
    And the input text is "Any text works here."
    When the procedure runs
    Then the output label should be "B"
    And the output arm should be 1
    And the procedure should complete successfully
]])
