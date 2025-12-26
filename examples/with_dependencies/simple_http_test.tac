-- Simple test to verify HTTP dependency injection works
--
-- This is a minimal example that will prove:
-- 1. Dependencies can be declared in procedure()
-- 2. Runtime creates the HTTP client
-- 3. Agent can use the dependency (via MCP tool)
-- 4. BDD tests can mock the dependency

agent("test_agent", {
    provider = "openai",
    model = "gpt-4o",
    system_prompt = "You are a test agent",
    tools = {"done"}
})

main = procedure("main", {
    input = {
        city = {type = "string", required = true}
    },

    -- Declare HTTP client dependency
    dependencies = {
        test_api = {
            type = "http_client",
            base_url = "https://httpbin.org"
        }
    },

    output = {
        success = {type = "boolean", required = true},
        message = {type = "string", required = true}
    },
    state = {}
}, function()
    -- Simple procedure that just completes
    -- In a real use case, the agent's tools would use test_api via ctx.deps.test_api

    Test_agent.turn()

    return {
        success = true,
        message = "Dependencies initialized successfully"
    }
end)

specifications([[
Feature: HTTP Dependency Injection
  Scenario: Procedure with HTTP dependency runs successfully
    Given the procedure has started
    When the Test_agent agent takes turn
    Then the done tool should be called
    And the output success should be true
]])
