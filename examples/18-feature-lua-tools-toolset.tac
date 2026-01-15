--[[
Example: Lua Toolset with type="lua"

Demonstrates defining a toolset containing multiple Lua function tools.
This approach is useful when you have a related set of tools that logically
belong together.

To run this example:
tactus run examples/18-feature-lua-tools-toolset.tac --param operation="add 15 and 27"
]]--

-- Import completion tool from standard library
local done = require("tactus.tools.done")

-- Define a toolset containing multiple math tools
Toolset "math_tools" {
    type = "lua",
    tools = {
        {
            name = "add",
            description = "Add two numbers together",
            input = {
                a = field.number{required = true, description = "First number"},
                b = field.number{required = true, description = "Second number"}
            },
            handler = function(args)
                local result = args.a + args.b
                return string.format("%g + %g = %g", args.a, args.b, result)
            end
        },
        {
            name = "subtract",
            description = "Subtract second number from first",
            input = {
                a = field.number{required = true, description = "First number"},
                b = field.number{required = true, description = "Second number"}
            },
            handler = function(args)
                local result = args.a - args.b
                return string.format("%g - %g = %g", args.a, args.b, result)
            end
        },
        {
            name = "multiply",
            description = "Multiply two numbers",
            input = {
                a = field.number{required = true, description = "First number"},
                b = field.number{required = true, description = "Second number"}
            },
            handler = function(args)
                local result = args.a * args.b
                return string.format("%g × %g = %g", args.a, args.b, result)
            end
        },
        {
            name = "divide",
            description = "Divide first number by second",
            input = {
                a = field.number{required = true, description = "Numerator"},
                b = field.number{required = true, description = "Denominator"}
            },
            handler = function(args)
                if args.b == 0 then
                    return "Error: Division by zero"
                end
                local result = args.a / args.b
                return string.format("%g ÷ %g = %g", args.a, args.b, result)
            end
        },
        {
            name = "power",
            description = "Raise first number to the power of second",
            input = {
                base = field.number{required = true, description = "Base number"},
                exponent = field.number{required = true, description = "Exponent"}
            },
            handler = function(args)
                local result = args.base ^ args.exponent
                return string.format("%g ^ %g = %g", args.base, args.exponent, result)
            end
        },
        {
            name = "square_root",
            description = "Calculate square root of a number",
            input = {
                number = field.number{required = true, description = "Number to find square root of"}
            },
            handler = function(args)
                if args.number < 0 then
                    return "Error: Cannot calculate square root of negative number"
                end
                local result = math.sqrt(args.number)
                return string.format("√%g = %g", args.number, result)
            end
        }
    }
}

-- Agent with access to the math toolset
mathematician = Agent {
    provider = "openai",
    model = "gpt-4o-mini",
    tool_choice = "required",
    system_prompt = [[You are a helpful mathematics assistant.

IMPORTANT: You MUST call the appropriate math tool for EVERY calculation. Never calculate directly.

Available tools:
- add: Add two numbers
- subtract: Subtract numbers
- multiply: Multiply numbers
- divide: Divide numbers
- power: Calculate powers
- square_root: Calculate square roots

After calling the math tool, call done with the result.]],
    initial_message = "{input.operation}",
    tools = {
        "math_tools",
        done,
    }
}

-- Main workflow

Procedure {
    input = {
            operation = field.string{description = "Mathematical operation to perform", default = "What is 5 plus 3?"}
    },
    output = {
            answer = field.string{required = true, description = "The mathematical answer"},
            completed = field.boolean{required = true, description = "Whether the task was completed"}
    },
    function(input)

    local max_turns = 10
        local turn_count = 0
        local result

        repeat
            result = mathematician()
            turn_count = turn_count + 1

            -- Log tool usage
            local tools_used = {}
            for _, tool_name in ipairs({"add", "subtract", "multiply", "divide", "power", "square_root"}) do
                if Tool.called(tool_name) then
                    table.insert(tools_used, tool_name)
                end
            end
            if #tools_used > 0 then
                Log.info("Used tools: " .. table.concat(tools_used, ", "))
            end

        until done.called() or turn_count >= max_turns

        -- Get final result
        local answer
        if done.called() then
            answer = done.last_result() or "Task completed"
        else
            answer = result and tostring(result.output) or ""
        end

        return {
            answer = answer,
            completed = done.called()
        }

    -- BDD Specifications
    end
}

Specification([[
Feature: Lua Toolset with Multiple Tools
  Demonstrate toolset() with type="lua" for grouped tools

  Scenario: Mathematician calculates 5 plus 3
    Given the procedure has started
    And the agent "mathematician" responds with "The calculation result is 8."
    And the agent "mathematician" calls tool "add" with args {"a": 5, "b": 3}
    And the agent "mathematician" calls tool "done" with args {"reason": "5 + 3 = 8"}
    When the procedure runs
    Then the procedure should complete successfully
    And the output completed should be True
    And the add tool should be called
    And the done tool should be called
    And the output answer should exist
]])
