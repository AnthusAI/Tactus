--[[
Advanced Toolset Features Example

Demonstrates:
1. Config-defined toolsets (from .tac.yml)
2. Toolset filtering by tool name (include/exclude)
3. Toolset prefixing for namespacing
4. Toolset renaming for custom names
5. Combined toolsets merging multiple sources
6. Per-agent toolset customization

To run:
tactus run examples/16-feature-toolsets-advanced.tac --param task="Calculate a mortgage"
]]--

-- Agent 1: Uses config-defined combined toolset
agent("analyst", {
    provider = "openai",
    model = "gpt-4o-mini",
    system_prompt = [[You are a financial analyst with access to calculation tools.
List the available tools and then call the done tool.]],
    initial_message = "What tools do you have available?",
    toolsets = {
        "all_tools"  -- References combined toolset from config
    }
})

-- Agent 2: Uses filtering to include only specific tools
agent("calculator", {
    provider = "openai",
    model = "gpt-4o-mini",
    system_prompt = [[You are a calculator with access to mathematical functions.
List your tools and call done when finished.]],
    initial_message = "What mathematical tools can you use?",
    toolsets = {
        -- Include only specific tools from plugin toolset
        {name = "plugin", include = {"calculate_mortgage", "compound_interest"}},
        "done"
    }
})

-- Agent 3: Uses prefixing for namespacing
agent("prefixed_agent", {
    provider = "openai",
    model = "gpt-4o-mini",
    system_prompt = [[You have prefixed tools. List them and call done.]],
    initial_message = "Show me your prefixed tools",
    toolsets = {
        -- Add calc_ prefix to all tools from plugin
        {name = "plugin", prefix = "calc_"},
        "done"
    }
})

-- Agent 4: Uses exclusion to remove specific tools
agent("restricted", {
    provider = "openai",
    model = "gpt-4o-mini",
    system_prompt = [[You have most tools except excluded ones. List them and call done.]],
    initial_message = "What tools do you have?",
    toolsets = {
        -- Exclude specific tools from plugin toolset
        {name = "plugin", exclude = {"web_search", "wikipedia_lookup"}},
        "done"
    }
})

-- Agent 5: Explicitly no tools (for observation/analysis only)
agent("observer", {
    provider = "openai",
    model = "gpt-4o-mini",
    system_prompt = [[You are an observer with no tools. Just respond with your observation.]],
    initial_message = "Observe that you have no tools available.",
    toolsets = {}  -- Explicitly empty - NO tools at all
})

-- Main procedure demonstrating each agent
procedure({
    outputs = {
        analyst_tools = {
            type = "string",
            description = "Tools available to analyst"
        },
        calculator_tools = {
            type = "string",
            description = "Tools available to calculator"
        },
        prefixed_tools = {
            type = "string",
            description = "Tools available to prefixed agent"
        },
        restricted_tools = {
            type = "string",
            description = "Tools available to restricted agent"
        },
        observer_response = {
            type = "string",
            description = "Observer's response about having no tools"
        }
    }
}, function()
    Log.info("=== Advanced Toolset Features Demo ===")

    -- Helper function to run agent with max turns
    local function run_agent_with_limit(agent_name, agent_ref, max_turns)
        Log.info("Testing " .. agent_name)
        local result
        local turn_count = 0

        repeat
            result = agent_ref.turn()
            turn_count = turn_count + 1
        until Tool.called("done") or turn_count >= max_turns

        local response = result.text
        Log.info(agent_name .. " response", {text = response})
        return response
    end

    -- Test Agent 1: Combined toolsets from config
    local analyst_response = run_agent_with_limit("Agent 1: Combined toolsets", Analyst, 2)

    -- Test Agent 2: Filtered toolset (include specific tools)
    local calculator_response = run_agent_with_limit("Agent 2: Filtered toolset (include)", Calculator, 2)

    -- Test Agent 3: Prefixed toolset
    local prefixed_response = run_agent_with_limit("Agent 3: Prefixed toolset", Prefixed_agent, 2)

    -- Test Agent 4: Restricted toolset (exclude specific tools)
    local restricted_response = run_agent_with_limit("Agent 4: Restricted toolset (exclude)", Restricted, 2)

    -- Test Agent 5: No tools (explicitly empty) - only needs 1 turn
    Log.info("Testing Agent 5: No tools")
    local observer_result = Observer.turn()
    local observer_response = observer_result.text
    Log.info("Observer response", {text = observer_response})

    return {
        analyst_tools = analyst_response,
        calculator_tools = calculator_response,
        prefixed_tools = prefixed_response,
        restricted_tools = restricted_response,
        observer_response = observer_response
    }
end)

-- BDD Specifications
specifications([[
Feature: Advanced Toolset Management
  Demonstrate toolset filtering, prefixing, renaming, and composition

  Scenario: Config-defined combined toolsets work
    Given the analyst agent has the combined toolset
    When the analyst agent lists its tools
    Then the analyst should have access to multiple toolset sources

  Scenario: Toolset filtering with include works
    Given the calculator agent uses include filtering
    When the calculator lists its tools
    Then the calculator should only have calculate_mortgage and compound_interest

  Scenario: Toolset prefixing works
    Given the prefixed_agent uses calc_ prefix
    When the prefixed_agent lists its tools
    Then all tool names should start with calc_

  Scenario: Toolset filtering with exclude works
    Given the restricted agent uses exclude filtering
    When the restricted agent lists its tools
    Then the restricted agent should not have web_search or wikipedia_lookup

  Scenario: Empty toolsets work
    Given the observer has toolsets = {}
    When the observer tries to act
    Then the observer should have no tools available
]])
