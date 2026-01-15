-- Example: Import Toolsets from Local .tac Files
-- Demonstrates importing tools and toolsets from other .tac files

-- Import completion tool from standard library
local done = require("tactus.tools.done")

-- Import all tools from a helper file
Toolset "imported_text_tools" {
    use = "./helpers/text_tools.tac"  -- Import from relative path
}

-- Agent that uses imported toolset
text_processor = Agent {
    provider = "openai",
    model = "gpt-4o-mini",
    system_prompt = [[You are a text processing assistant.

You have access to imported text processing tools:
- uppercase: Convert text to uppercase
- lowercase: Convert text to lowercase
- reverse: Reverse the text
- word_count: Count words in text

When asked to process text, use the appropriate tool.
After processing, call done with the result.]],

    tools = {"imported_text_tools", done},
}

-- Alternative: Import specific tools and combine with others
Toolset "combined_tools" {
    -- In a full implementation, this would combine:
    -- 1. Tools from the imported file
    -- 2. Other toolsets or individual tools
    tools = {"uppercase", "lowercase"}
}

-- Main procedure

Procedure {
    input = {
            operation = field.string{
                default = "uppercase",
                description = "Operation: uppercase, lowercase, reverse, or word_count"
            },
            text = field.string{
                default = "Hello from imported tools!",
                description = "Text to process"
            }
    },
    output = {
            result = field.string{required = true, description = "Processed text"},
            source = field.string{description = "Source of the tools used"},
            completed = field.boolean{required = true, description = "Whether task completed"}
    },
    function(input)

    Log.info("Starting toolset import demo", {
                operation = input.operation,
                text = input.text
            })

            -- Note: In the current partial implementation, .tac file imports
            -- return empty toolsets. In a full implementation, this would:
            -- 1. Parse the imported .tac file
            -- 2. Extract all Tool and Toolset definitions
            -- 3. Make them available to the agent

            Log.warning(
                "Note: .tac file toolset imports are partially implemented. " ..
                "Full implementation would extract tools from ./helpers/text_tools.tac"
            )

            -- For demonstration, we'll show what the full implementation would do
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
                if turn_count == 0 then
                    result = text_processor({message = message})
                else
                    result = text_processor()
                end
                turn_count = turn_count + 1
            until done.called() or turn_count >= max_turns

            -- Get result
            local answer = "Task not completed (partial implementation)"
            local completed = false
            local source = "imported from ./helpers/text_tools.tac"

            if done.called() then
                completed = true
                local call = done.last_call()
                if call and call.args then
                    local ok, reason = pcall(function() return call.args["reason"] end)
                    if ok and reason then
                        answer = reason
                    end
                end
            elseif result and result.output ~= nil then
                answer = tostring(result.output)
            end

            Log.info("Import result", {
                completed = completed,
                source = source,
                result = answer
            })

            return {
                result = answer,
                source = source,
                completed = completed
            }

    -- BDD Specifications
    end
}

Specification([[
Feature: Import Toolsets from Local .tac Files
  Demonstrate importing tools and toolsets from other .tac files

  Scenario: Import toolset demo runs
    Given the procedure has started
    And the agent "text_processor" responds with "I've processed the text using imported tools."
    And the agent "text_processor" calls tool "done" with args {"reason": "HELLO - processed with imported tools"}
    When the procedure runs
    Then the done tool should be called
    And the output result should exist
    And the output source should exist
    And the procedure should complete successfully
]])

-- Implementation Notes:
--
-- Full implementation would:
-- 1. Parse the imported .tac file using the Lua DSL parser
-- 2. Extract all Tool and Toolset definitions
-- 3. Register them in a sub-registry to avoid conflicts
-- 4. Create a combined toolset with all extracted tools
-- 5. Support recursive imports (imported files can import other files)
-- 6. Handle circular import detection
-- 7. Provide namespace isolation to prevent naming conflicts
--
-- Current partial implementation:
-- - Validates the file path
-- - Checks that the file exists and is a .tac file
-- - Returns an empty toolset with a warning
-- - Demonstrates the intended usage pattern
