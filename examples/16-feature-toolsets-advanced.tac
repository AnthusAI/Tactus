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

-- Import completion tool from standard library
local done = require("tactus.tools.done")

-- Agent 1: Uses config-defined combined toolset
analyst = Agent {
    provider = "openai",
    model = "gpt-4o-mini",
    system_message = [[You are a financial analyst with access to calculation tools.
List the available tools and then call the done Tool.]],
    initial_message = "What tools do you have available?",
    toolsets = {
        "all_tools"  -- References combined toolset from config
    },
    tools = {done}
}

-- Agent 2: Uses filtering to include only specific tools
calculator = Agent {
    provider = "openai",
    model = "gpt-4o-mini",
    system_message = [[You are a calculator with access to mathematical functions.
List your tools and call done when finished.]],
    initial_message = "What mathematical tools can you use?",
    toolsets = {
        -- Include only specific tools from plugin toolset
        {name = "plugin", include = {"calculate_mortgage", "compound_interest"}}
    },
    tools = {done}
}

-- Agent 3: Uses prefixing for namespacing
prefixed_agent = Agent {
    provider = "openai",
    model = "gpt-4o-mini",
    system_message = [[You have prefixed tools. List them and call done.]],
    initial_message = "Show me your prefixed tools",
    toolsets = {
        -- Add calc_ prefix to all tools from plugin
        {name = "plugin", prefix = "calc_"}
    },
    tools = {done}
}

-- Agent 4: Uses exclusion to remove specific tools
restricted = Agent {
    provider = "openai",
    model = "gpt-4o-mini",
    system_message = [[You have most tools except excluded ones. List them and call done.]],
    initial_message = "What tools do you have?",
    toolsets = {
        -- Exclude specific tools from plugin toolset
        {name = "plugin", exclude = {"web_search", "wikipedia_lookup"}}
    },
    tools = {done}
}

-- Agent 5: Explicitly no tools (for observation/analysis only)
observer = Agent {
    provider = "openai",
    model = "gpt-4o-mini",
    system_message = [[You are an observer with no tools. Just respond with your observation.]],
    initial_message = "Observe that you have no tools available.",
    toolsets = {}  -- Explicitly empty - NO tools at all
}

-- Main procedure demonstrating each agent

Procedure {
    output = {
            analyst_tools = field.string{description = "Tools available to analyst"},
            calculator_tools = field.string{description = "Tools available to calculator"},
            prefixed_tools = field.string{description = "Tools available to prefixed agent"},
            restricted_tools = field.string{description = "Tools available to restricted agent"},
            observer_response = field.string{description = "Observer's response about having no tools"}
    },
    function(input)

    Log.info("=== Advanced Toolset Features Demo ===")

        -- Helper function to run agent with max turns
        local function run_agent_with_limit(agent_name, agent_ref, max_turns)
            Log.info("Testing " .. agent_name)
            local result
            local turn_count = 0

            repeat
                result = agent_ref()
                turn_count = turn_count + 1
            until done.called() or turn_count >= max_turns

            local response = result.message
            Log.info(agent_name .. " response", {text = response})
            return response
        end

        -- Test Agent 1: Combined toolsets from config
        local analyst_response = run_agent_with_limit("Agent 1: Combined toolsets", analyst, 2)

        -- Test Agent 2: Filtered toolset (include specific tools)
        local calculator_response = run_agent_with_limit("Agent 2: Filtered toolset (include)", calculator, 2)

        -- Test Agent 3: Prefixed toolset
        local prefixed_response = run_agent_with_limit("Agent 3: Prefixed toolset", prefixed_agent, 2)

        -- Test Agent 4: Restricted toolset (exclude specific tools)
        local restricted_response = run_agent_with_limit("Agent 4: Restricted toolset (exclude)", restricted, 2)

        -- Test Agent 5: No tools (explicitly empty) - only needs 1 turn
        Log.info("Testing Agent 5: No tools")
        local observer_result = observer()
        local observer_response = observer_result.message
        Log.info("Observer response", {text = observer_response})

        return {
            analyst_tools = analyst_response,
            calculator_tools = calculator_response,
            prefixed_tools = prefixed_response,
            restricted_tools = restricted_response,
            observer_response = observer_response
        }

    -- BDD Specifications
    end
}

Specifications([[
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
