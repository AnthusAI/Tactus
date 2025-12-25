-- Time Lookup Example with HTTP Dependency
--
-- This example demonstrates:
-- 1. Declaring an HTTP client dependency
-- 2. Dependencies are initialized by the runtime
-- 3. Testing with mocked responses (fast)
-- 4. Testing with real API calls (integration)
--
-- Uses worldtimeapi.org - a free API with no authentication required
--
-- NOTE: In a full implementation, the time_api dependency would be
-- exposed as an MCP tool that the agent can call. For now, this
-- example just demonstrates that dependencies are properly initialized.

agent("time_agent", {
    provider = "openai",
    model = "gpt-4o",
    system_prompt = [[
You are a helpful agent.

For this test, just call done immediately.

Available tools:
- done: Mark task as complete
]],
    tools = {"done"}
})

procedure({
    input = {
        timezone = {
            type = "string",
            required = true,
            description = "Timezone to look up (e.g., 'America/New_York')"
        }
    },

    dependencies = {
        time_api = {
            type = "http_client",
            base_url = "http://worldtimeapi.org/api",
            timeout = 10.0
        }
    },

    output = {
        datetime = {type = "string", required = true},
        timezone = {type = "string", required = true}
    },
    state = {}
}, function()
    -- Execute agent turn
    Time_agent.turn()

    return {
        datetime = "dependency_test",
        timezone = input.timezone
    }
end)

-- BDD Specifications

specifications([[
Feature: Time Lookup with Dependencies
  Scenario: Dependency is initialized and procedure runs
    Given the procedure has started
    When the Time_agent agent takes turn
    Then the done tool should be called
    And the output datetime should be "dependency_test"
    And the output timezone should exist
]])
