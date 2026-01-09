--[[
Example: Inline Lua Function Tools

Demonstrates defining tools inline within agent configuration.
This approach is useful for agent-specific tools that aren't reused elsewhere.

To run this example:
tactus run examples/18-feature-lua-tools-inline.tac --param message="Hello, World!"
]]--

-- Define completion tool
Tool "done" { use = "tactus.done" }

-- Agent with inline Lua function tools
Agent "text_processor" {
    provider = "openai",
    model = "gpt-4o-mini",
    tool_choice = "required",
    system_prompt = [[You are a text processing assistant.

IMPORTANT: You MUST call the appropriate tool for EVERY request. Never process text directly.

Available tools:
- uppercase: Convert text to uppercase
- lowercase: Convert text to lowercase
- reverse_text: Reverse the order of characters
- count_words: Count words in text
- repeat_text: Repeat text a specified number of times

After calling the tool, call done with the tool's result.]],
    initial_message = "{input.message}",
    -- Inline tool definitions specific to this agent
    tools = {
        {
            name = "uppercase",
            description = "Convert text to uppercase",
            input = {
                text = field.string{required = true, description = "Text to convert"}
            },
            handler = function(args)
                return string.upper(args.text)
            end
        },
        {
            name = "lowercase",
            description = "Convert text to lowercase",
            input = {
                text = field.string{required = true, description = "Text to convert"}
            },
            handler = function(args)
                return string.lower(args.text)
            end
        },
        {
            name = "reverse_text",
            description = "Reverse the order of characters in text",
            input = {
                text = field.string{required = true, description = "Text to reverse"}
            },
            handler = function(args)
                return string.reverse(args.text)
            end
        },
        {
            name = "count_words",
            description = "Count the number of words in text",
            input = {
                text = field.string{required = true, description = "Text to analyze"}
            },
            handler = function(args)
                local count = 0
                for word in string.gmatch(args.text, "%S+") do
                    count = count + 1
                end
                return string.format("Word count: %d", count)
            end
        },
        {
            name = "repeat_text",
            description = "Repeat text a specified number of times",
            input = {
                text = field.string{required = true, description = "Text to repeat"},
                times = field.integer{required = true, description = "Number of repetitions"}
            },
            handler = function(args)
                local result = {}
                for i = 1, args.times do
                    table.insert(result, args.text)
                end
                return table.concat(result, " ")
            end
        }
    },
    toolsets = {
        "done"  -- Can still use regular toolsets alongside inline tools
    }
}

-- Main workflow

input {
        message = field.string{description = "Text processing request", default = "Convert 'hello world' to uppercase"}
    }

output {
        result = field.string{required = true, description = "The processed result"},
        tools_used = field.array{required = false, description = "List of tools that were used"},
        completed = field.boolean{required = true, description = "Whether the task was completed"}
    }

local max_turns = 5
    local turn_count = 0
    local result

    repeat
        result = Agent("text_processor").turn()
        turn_count = turn_count + 1

    until Tool.called("done") or turn_count >= max_turns

    -- Track which tools were used
    local tools_used = {}
    for _, tool_name in ipairs({
        "text_processor_uppercase",
        "text_processor_lowercase",
        "text_processor_reverse_text",
        "text_processor_count_words",
        "text_processor_repeat_text"
    }) do
        if Tool.called(tool_name) then
            -- Remove agent name prefix for display
            local display_name = string.gsub(tool_name, "text_processor_", "")
            table.insert(tools_used, display_name)
        end
    end

    -- Get final result
    local answer
    if Tool.called("done") then
        answer = Tool.last_result("done") or "Task completed"
    else
        answer = result.text
    end

    if #tools_used > 0 then
        Log.info("Tools used: " .. table.concat(tools_used, ", "))
    end

    return {
        result = answer,
        tools_used = tools_used,
        completed = Tool.called("done")
    }

-- BDD Specifications
Specifications([[
Feature: Inline Lua Function Tools
  Demonstrate inline tool definitions in agent configuration

  Scenario: Text processor converts 'hello world' to uppercase
    Given the procedure has started
    When the procedure runs
    Then the procedure should complete successfully
    And the output completed should be True
    And the text_processor_uppercase tool should be called
    And the text_processor_uppercase tool should be called with text="hello world"
    And the output result should be similar to "HELLO WORLD"
]])
