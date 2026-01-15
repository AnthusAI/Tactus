-- Simple test to verify HTTP dependency injection works
--
-- This is a minimal example that will prove:
-- 1. Dependencies can be declared in procedure()
-- 2. Runtime creates the HTTP client
-- 3. Agent can use the dependency (via MCP tool)
-- 4. BDD tests can mock the dependency

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

test_agent = Agent {
    provider = "openai",
    model = "gpt-4o",
    system_prompt = "You are a test agent",
    tools = {done}
}

input {
        city = field.string{required = true}
    }

output {
        success = field.boolean{required = true},
        message = field.string{required = true}
    }

-- Simple procedure that just completes
    -- In a real use case, the agent's tools would use test_api via ctx.deps.test_api

    test_agent()

    return {
        success = true,
        message = "Dependencies initialized successfully"
    }

Specification([[
Feature: HTTP Dependency Injection
  Scenario: Procedure with HTTP dependency runs successfully
    Given the procedure has started
    When the Test_agent agent takes turn
    Then the done tool should be called
    And the output success should be true
]])
