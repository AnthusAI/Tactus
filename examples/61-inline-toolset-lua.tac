-- Example: Inline Lua Tools in Toolset Declarations
-- Demonstrates defining Lua function tools directly within a Toolset block

-- Import completion tool from standard library
local done = require("tactus.tools.done")

-- Define a Toolset with inline Lua tools
Toolset "text_tools" {
    tools = {
        {
            name = "uppercase",
            description = "Convert text to uppercase",
            input = {
                text = field.string{required = true, description = "Text to convert"}
            },
            function(args)
                return args.text:upper()
            end
        },
        {
            name = "lowercase",
            description = "Convert text to lowercase",
            input = {
                text = field.string{required = true, description = "Text to convert"}
            },
            function(args)
                return args.text:lower()
            end
        },
        {
            name = "reverse",
            description = "Reverse the text",
            input = {
                text = field.string{required = true, description = "Text to reverse"}
            },
            function(args)
                return string.reverse(args.text)
            end
        },
        {
            name = "word_count",
            description = "Count words in text",
            input = {
                text = field.string{required = true, description = "Text to analyze"}
            },
            function(args)
                local count = 0
                for word in string.gmatch(args.text, "%S+") do
                    count = count + 1
                end
                return string.format("%d words", count)
            end
        }
    }
}

-- Agent that uses the inline toolset
text_processor = Agent {
    provider = "openai",
    model = "gpt-4o-mini",
    system_prompt = [[You are a text processing assistant.

Available tools:
- uppercase: Convert text to uppercase
- lowercase: Convert text to lowercase
- reverse: Reverse the text
- word_count: Count words in text

When asked to process text, use the appropriate tool.
After processing, call done with the result.]],

    tools = {"text_tools", done},
}

-- Main procedure

Procedure {
    input = {
            operation = field.string{
                default = "uppercase",
                description = "Operation to perform: uppercase, lowercase, reverse, or word_count"
            },
            text = field.string{
                default = "Hello, World!",
                description = "Text to process"
            }
    },
    output = {
            result = field.string{required = true, description = "Processed text"},
            completed = field.boolean{required = true, description = "Whether task completed"}
    },
    function(input)

    Log.info("Starting inline toolset demo", {
                operation = input.operation,
                text = input.text
            })

            -- Construct message for agent
            local message = string.format(
                "Please %s the following text: '%s'",
                input.operation,
                input.text
            )

            -- Run agent with limit
            local max_turns = 3
            local turn_count = 0
            local result

            repeat
                result = text_processor({message = message})
                turn_count = turn_count + 1
                message = nil  -- Only use initial message on first turn
            until done.called() or turn_count >= max_turns

            -- Get result
            local answer = "Task not completed"
            local completed = false

            if done.called() then
                completed = true
                local call = done.last_call()
                if call and call.args then
                    local ok, reason = pcall(function() return call.args["reason"] end)
                    if ok and reason then
                        answer = reason
                    end
                end
            elseif result and result.message then
                answer = tostring(result.output)
            end

            Log.info("Task completed", {result = answer, completed = completed})

            return {
                result = answer,
                completed = completed
            }

    -- BDD Specifications
    end
}

Specification([[
Feature: Inline Lua Tools in Toolset Declarations
  Demonstrate defining Lua function tools directly within a Toolset block

  Scenario: Convert text to uppercase
    Given the procedure has started
    And the message is "Please uppercase the following text: 'Hello, World!'"
    And the agent "text_processor" responds with "I've converted the text to uppercase."
    And the agent "text_processor" calls tool "text_tools_uppercase" with args {"text": "Hello, World!"}
    And the agent "text_processor" calls tool "done" with args {"reason": "HELLO, WORLD!"}
    When the procedure runs
    Then the done tool should be called
    And the output result should exist
    And the output completed should be True
    And the procedure should complete successfully
]])
