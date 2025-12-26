--[[
Example: Lua Toolset with type="lua"

Demonstrates defining a toolset containing multiple Lua function tools.
This approach is useful when you have a related set of tools that logically
belong together.

To run this example:
tactus run examples/18-feature-lua-tools-toolset.tac --param operation="add 15 and 27"
]]--

-- Define a toolset containing multiple math tools
toolset("math_tools", {
    type = "lua",
    tools = {
        {
            name = "add",
            description = "Add two numbers together",
            parameters = {
                a = {type = "number", description = "First number", required = true},
                b = {type = "number", description = "Second number", required = true}
            },
            handler = function(args)
                local result = args.a + args.b
                return string.format("%g + %g = %g", args.a, args.b, result)
            end
        },
        {
            name = "subtract",
            description = "Subtract second number from first",
            parameters = {
                a = {type = "number", description = "First number", required = true},
                b = {type = "number", description = "Second number", required = true}
            },
            handler = function(args)
                local result = args.a - args.b
                return string.format("%g - %g = %g", args.a, args.b, result)
            end
        },
        {
            name = "multiply",
            description = "Multiply two numbers",
            parameters = {
                a = {type = "number", description = "First number", required = true},
                b = {type = "number", description = "Second number", required = true}
            },
            handler = function(args)
                local result = args.a * args.b
                return string.format("%g × %g = %g", args.a, args.b, result)
            end
        },
        {
            name = "divide",
            description = "Divide first number by second",
            parameters = {
                a = {type = "number", description = "Numerator", required = true},
                b = {type = "number", description = "Denominator", required = true}
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
            parameters = {
                base = {type = "number", description = "Base number", required = true},
                exponent = {type = "number", description = "Exponent", required = true}
            },
            handler = function(args)
                local result = args.base ^ args.exponent
                return string.format("%g ^ %g = %g", args.base, args.exponent, result)
            end
        },
        {
            name = "square_root",
            description = "Calculate square root of a number",
            parameters = {
                number = {type = "number", description = "Number to find square root of", required = true}
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
})

-- Agent with access to the math toolset
agent("mathematician", {
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
    toolsets = {
        "math_tools",  -- Reference the entire toolset
        "done"
    }
})

-- Main workflow
main = procedure("main", {
    input = {
        operation = {
            type = "string",
            default = "What is 5 plus 3?",
            description = "Mathematical operation to perform"
        }
    },
    output = {
        answer = {
            type = "string",
            required = true,
            description = "The mathematical answer"
        },
        completed = {
            type = "boolean",
            required = true,
            description = "Whether the task was completed"
        }
    },
    state = {}
}, function()
    local max_turns = 10
    local turn_count = 0
    local result

    repeat
        result = Mathematician.turn()
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

    until Tool.called("done") or turn_count >= max_turns

    -- Get final result
    local answer
    if Tool.called("done") then
        answer = Tool.last_call("done").args.reason
    else
        answer = result.text
    end

    return {
        answer = answer,
        completed = Tool.called("done")
    }
end)

-- BDD Specifications
specifications([[
Feature: Lua Toolset with Multiple Tools
  Demonstrate toolset() with type="lua" for grouped tools

  Scenario: Mathematician calculates 5 plus 3
    Given the procedure has started
    When the procedure runs
    Then the procedure should complete successfully
    And the output completed should be True
    And the add tool should be called
    And the add tool should be called with a=5
    And the add tool should be called with b=3
    And the output answer should be similar to "8"
]])
