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
    system_message = [[You are a text processing assistant.

Available tools:
- uppercase: Convert text to uppercase
- lowercase: Convert text to lowercase
- reverse: Reverse the text
- word_count: Count words in text

When asked to process text, use the appropriate tool.
After processing, call done with the result.]],

    toolsets = {"text_tools", "done"}
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
                answer = result.message
            end

            Log.info("Task completed", {result = answer, completed = completed})

            return {
                result = answer,
                completed = completed
            }

    -- BDD Specifications
    end
}

Specifications([[
Feature: Inline Lua Tools in Toolset Declarations
  Demonstrate defining Lua function tools directly within a Toolset block

  Scenario: Convert text to uppercase
    Given the procedure has started
    When the procedure runs with operation "uppercase" and text "hello world"
    Then the text_tools_uppercase tool should be called
    And the done tool should be called
    And the output result should contain "HELLO WORLD"
    And the output completed should be True

  Scenario: Count words in text
    Given the procedure has started
    When the procedure runs with operation "word_count" and text "one two three four five"
    Then the text_tools_word_count tool should be called
    And the done tool should be called
    And the output result should contain "5 words"
    And the output completed should be True
]])
