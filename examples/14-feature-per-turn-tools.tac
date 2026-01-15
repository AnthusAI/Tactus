-- Per-Turn Tool Control Example
-- Demonstrates dynamic tool availability using both tools and toolsets

-- Define individual tools
search = Tool {
    description = "Search for information",
    input = {
        query = field.string{required = true, description = "Search query"}
    },
    function(args)
        return "Results for: " .. args.query
    end
}

analyze = Tool {
    description = "Analyze data",
    input = {
        data = field.string{required = true, description = "Data to analyze"}
    },
    function(args)
        return "Analysis of: " .. args.data
    end
}

local done = require("tactus.tools.done")

-- Define a toolset for math operations
add = Tool {
    description = "Add two numbers",
    input = {
        a = field.number{required = true},
        b = field.number{required = true}
    },
    function(args)
        return args.a + args.b
    end
}

multiply = Tool {
    description = "Multiply two numbers",
    input = {
        a = field.number{required = true},
        b = field.number{required = true}
    },
    function(args)
        return args.a * args.b
    end
}

-- Create math_tools toolset (collection of related tools)
Toolset "math_tools" {
    tools = {"add", "multiply"}
}

-- Agent with no tools initially defined
worker = Agent {
    provider = "openai",
    system_prompt = [[You are a helpful assistant. Use the available tools to complete tasks.
When you have completed your task, call the 'done' Tool.]],
    initial_message = "I'm ready to help. What would you like me to do?",
    tools = {},  -- Empty - will control per-turn
}

Procedure {
    output = {
            result = field.string{required = true}
    },
    function(input)

    Log.info("Starting per-turn tool control example")

            -- Turn 1: Only search tool available
            Log.info("Turn 1: Only search tool")
            worker({
                message = "Search for information about Lua programming",
                tools = {"search"}  -- Only search tool
            })

            -- Turn 2: Math toolset available
            Log.info("Turn 2: Math toolset")
            worker({
                message = "Calculate: (5 + 3) * 2",
                tools = {math_tools}  -- Math toolset
            })

            -- Turn 3: Multiple individual tools
            Log.info("Turn 3: Search and analyze tools")
            worker({
                message = "Search for 'weather' and analyze the results",
                tools = {"search", "analyze"}  -- Multiple tools
            })

            -- Turn 4: Combination of tools and toolsets
            Log.info("Turn 4: Combined tools and toolsets")
            worker({
                message = "Calculate 10 + 20, then search for the result, and signal completion",
                tools = {"search", "done", math_tools}  -- Individual tools plus math toolset
            })

            -- Turn 5: No tools at all
            Log.info("Turn 5: No tools")
            local result = worker({
                message = "Tell me a joke (no tools available)",
                tools = {}  -- Explicitly no tools
            })

            -- Turn 6: Default tools (None means use agent's default)
            Log.info("Turn 6: Default tools")
            worker({
                message = "Use any available tools",
                tools = nil  -- Use agent's defaults
            })

            return {
                result = "Demonstrated per-turn tool control"
            }

    -- BDD Specifications
    end
}

Specification([[
Feature: Per-Turn Tool Control
  Demonstrate dynamic tool availability control

  Scenario: Control tools per turn
    Given the procedure has started
    And the agent "worker" responds with "I'm ready to help with the task."
    When the procedure runs
    Then the procedure should complete successfully
]])
