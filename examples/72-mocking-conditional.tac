-- Example: Conditional Mocking
-- Demonstrates mocking that returns different values based on input

-- Import completion tool from standard library
local done = require("tactus.tools.done")

-- Define tools that will be mocked
translate = Tool {
    description = "Translate English text to Spanish",
    input = {
        text = field.string{required = true, description = "Text to translate"}
    },
    function(args)
        return {translation = "default translation", language = "Spanish"}
    end
}

calculate = Tool {
    description = "Perform math operations",
    input = {
        operation = field.string{required = true, description = "Operation: add, multiply, divide, subtract"},
        x = field.number{required = true, description = "First number"},
        y = field.number{required = true, description = "Second number"}
    },
    function(args)
        return {result = 0}
    end
}

-- Conditional mocks - return based on input parameters
Mocks {
    translate = {
        conditional = {
            {when = {text = "hello"}, returns = {translation = "hola", language = "Spanish"}},
            {when = {text = "goodbye"}, returns = {translation = "adiós", language = "Spanish"}},
            {when = {text = "thank you"}, returns = {translation = "gracias", language = "Spanish"}},
            {when = {text = "yes"}, returns = {translation = "sí", language = "Spanish"}},
            {when = {text = "no"}, returns = {translation = "no", language = "Spanish"}}
        }
    },
    calculate = {
        conditional = {
            {when = {operation = "add", x = 5, y = 3}, returns = {result = 8}},
            {when = {operation = "multiply", x = 4, y = 7}, returns = {result = 28}},
            {when = {operation = "divide", x = 10, y = 2}, returns = {result = 5}},
            {when = {operation = "subtract", x = 9, y = 4}, returns = {result = 5}}
        }
    },
    -- Agent mock for CI testing
    assistant = {
        tool_calls = {
            {tool = "translate", args = {text = "hello"}},
            {tool = "done", args = {reason = "The translation of 'hello' is 'hola' in Spanish."}}
        },
        message = "I've translated the text."
    }
}

-- Agent that uses conditional tools
assistant = Agent {
    provider = "openai",
    model = "gpt-4o-mini",
    system_prompt = [[You are a helpful assistant with translation and calculation tools.

You have access to:
- translate: Translate English text to Spanish
- calculate: Perform math operations (add, multiply, divide, subtract)
- done: Signal completion

	Follow the user's instructions and use the appropriate tools.]],
    tools = {translate, calculate, done}
}

-- Main procedure

Procedure {
    input = {
            task_type = field.string{
                default = "translate",
                description = "Task type: translate or calculate"
            },
            input_value = field.string{
                default = "hello",
                description = "Input for the task"
            }
    },
    output = {
            result = field.string{required = true, description = "Task result"},
            tool_used = field.string{required = true, description = "Which tool was used"},
            completed = field.boolean{required = true, description = "Whether task completed"}
    },
    function(input)

    Log.info("Starting conditional mock demo", {
                task_type = input.task_type,
                input_value = input.input_value
            })

            -- Build appropriate message based on task type
            local message
            if input.task_type == "calculate" then
                -- Parse calculation from input_value (e.g., "5+3" -> add 5 and 3)
                if input.input_value == "5+3" then
                    message = "Please calculate: add 5 and 3, then call done with the result."
                elseif input.input_value == "4*7" then
                    message = "Please calculate: multiply 4 and 7, then call done with the result."
                elseif input.input_value == "10/2" then
                    message = "Please calculate: divide 10 by 2, then call done with the result."
                else
                    message = "Please calculate: subtract 4 from 9, then call done with the result."
                end
            else
                message = string.format(
                    "Please translate '%s' to Spanish and call done with the translation.",
                    input.input_value
                )
            end

            -- Run agent
            assistant({message = message})

            -- Wait for completion
            local max_turns = 3
            local turn_count = 1

            while not done.called() and turn_count < max_turns do
                assistant()
                turn_count = turn_count + 1
            end

            -- Determine which tool was used
            local tool_used = "none"
            if Tool.called("translate") then
                tool_used = "translate"
            elseif Tool.called("calculate") then
                tool_used = "calculate"
            end

            -- Get result from done call
            local result = "No result"
            if done.called() then
                local call = done.last_call()
                if call and call.args then
                    local ok, reason = pcall(function() return call.args["reason"] end)
                    if ok and reason then
                        result = reason
                    end
                end
            end

            Log.info("Conditional mock demo complete", {
                result = result,
                tool_used = tool_used,
                turns = turn_count
            })

            return {
                result = result,
                tool_used = tool_used,
                completed = done.called()
            }

    -- BDD Specifications
    end
}

Specifications([[
Feature: Conditional Mocking
  Tools return different values based on input parameters

  Scenario: Translate hello to Spanish
    Given the procedure has started
    When the procedure runs
    Then the translate tool should be called
    And the done tool should be called
    And the output completed should be True
    And the procedure should complete successfully
]])
