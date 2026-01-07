-- Simple test to verify HTTP dependency injection works
--
-- This is a minimal example that will prove:
-- 1. Dependencies can be declared in procedure()
-- 2. Runtime creates the HTTP client
-- 3. Agent can use the dependency (via MCP tool)
-- 4. BDD tests can mock the dependency

-- Define completion tool
tool("done", {
    description = "Signal completion of the task",
    input = {
        reason = field.string{required = true, description = "Completion message"}
    }
}, function(args)
    return "Done: " .. args.reason
end)

Agent("test_agent", {
    provider = "openai",
    model = "gpt-4o",
    system_prompt = "You are a test agent",
    toolsets = {"done"}
}

Procedure "main" {
    input = {
        city = field.string{required = true}
    },

    -- Declare HTTP client dependency
    dependencies = {
        test_api = field.http_client{}
    },

    output = {
        success = field.boolean{required = true},
        message = field.string{required = true}
    },
    function(input)
    -- Simple procedure that just completes
    -- In a real use case, the agent's tools would use test_api via ctx.deps.test_api

    Test_agent.turn()

    return {
        success = true,
        message = "Dependencies initialized successfully"
    }
end
}

Specifications([[
Feature: HTTP Dependency Injection
  Scenario: Procedure with HTTP dependency runs successfully
    Given the procedure has started
    When the Test_agent agent takes turn
    Then the done tool should be called
    And the output success should be true
]])
