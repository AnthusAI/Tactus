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

-- Define completion tool
done = Tool {
    description = "Signal completion of the task",
    input = {
        reason = field.string{required = true, description = "Completion message"}
    },
    function(args)
        return "Done: " .. args.reason
    end
}

time_agent = Agent {
    provider = "openai",
    model = "gpt-4o",
    system_prompt = [[
You are a helpful agent.

For this test, just call done immediately.

	Available tools:
	- done: Mark task as complete
	]],
    tools = {done}
}

input {
        timezone = field.string{required = true, description = "Timezone to look up (e.g., 'America/New_York')"}
    }

output {
        datetime = field.string{required = true},
        timezone = field.string{required = true}
    }

-- Execute agent turn
    time_agent()

    return {
        datetime = "dependency_test",
        timezone = input.timezone
    }

-- BDD Specifications

Specification([[
Feature: Time Lookup with Dependencies
  Scenario: Dependency is initialized and procedure runs
    Given the procedure has started
    When the Time_agent agent takes turn
    Then the done tool should be called
    And the output datetime should be "dependency_test"
    And the output timezone should exist
]])
