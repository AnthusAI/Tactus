-- Test loading indicators
test_agent = Agent {
  provider = "openai",
  model = "gpt-4o-mini",
  system_prompt = "You are a helpful assistant. Respond briefly.",
}

Specification([[
Feature: Loading indicator test

  Scenario: Procedure completes
    Given the procedure has started
    And the agent "test_agent" responds with "OK"
    When the procedure runs
    Then the output success should be true
]])

Procedure {
    output = {
      success = field.boolean{required = true}
    },
    function(input)

    Log.info("Starting test...")
      local result = test_agent()
      Log.info("Agent responded: " .. tostring(result.output))
      return {success = true}

    end
}
