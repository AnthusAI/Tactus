--[[
Example: Individual Lua Function Tools

Demonstrates defining tools using the tool() function.
Each tool() declaration creates a single-tool toolset that can be
referenced by name in agent configurations.

To run this example:
tactus run examples/18-feature-lua-tools-individual.tac --param task="Calculate 15% tip on a $50 bill"
]]--

-- Import completion tool from standard library
local done = require("tactus.tools.done")

-- Define individual tools using the tool() function
calculate_tip = Tool {
    description = "Calculate tip amount for a bill",
        input = {
            bill_amount = field.number{required = true, description = "Total bill amount in dollars"},
            tip_percentage = field.number{required = true, description = "Tip percentage (e.g., 15 for 15%)"},
        },
    function(args)
    local tip = args.bill_amount * (args.tip_percentage / 100)
    local total = args.bill_amount + tip
    return string.format("Bill: $%.2f, Tip (%.0f%%): $%.2f, Total: $%.2f",
        args.bill_amount, args.tip_percentage, tip, total)
end
}

split_bill = Tool {
    description = "Split a bill total among multiple people",
        input = {
            total_amount = field.number{required = true, description = "Total amount to split"},
            num_people = field.integer{required = true, description = "Number of people to split among"},
        },
    function(args)
    local per_person = args.total_amount / args.num_people
    return string.format("Split $%.2f among %d people = $%.2f per person",
        args.total_amount, args.num_people, per_person)
end
}

calculate_discount = Tool {
    description = "Calculate price after discount",
        input = {
            original_price = field.number{required = true, description = "Original price"},
            discount_percent = field.number{required = true, description = "Discount percentage"},
        },
    function(args)
    local discount_amount = args.original_price * (args.discount_percent / 100)
    local final_price = args.original_price - discount_amount
    return string.format("Original: $%.2f, Discount (%.0f%%): $%.2f, Final: $%.2f",
        args.original_price, args.discount_percent, discount_amount, final_price)
end
}

-- Agent with access to individual Lua tools
calculator = Agent {
    provider = "openai",
    model = "gpt-4o-mini",
    tool_choice = "required",
    system_prompt = [[You are a helpful calculator assistant.

IMPORTANT: You MUST call the appropriate tool for EVERY calculation. Never calculate directly.

After calling the calculation tool, call done with the result.]],
    initial_message = "{input.task}",
    tools = {
        -- Reference individual tools by name
        "calculate_tip",
        "split_bill",
        "calculate_discount",
        done,
    },
}

-- Main workflow
Procedure {
    input = {
        task = field.string{description = "Calculation task to perform", default = "Calculate 20% tip on $50"}
    },
    output = {
        result = field.string{required = true, description = "The calculation result"},
        completed = field.boolean{required = true, description = "Whether the task was completed successfully"}
    },
    function(input)
        local max_turns = 5
        local turn_count = 0
        local result

        repeat
            result = calculator()
            turn_count = turn_count + 1

            -- Log tool usage
            if Tool.called("calculate_tip") then
                Log.info("Used tip calculator")
            end
            if Tool.called("split_bill") then
                Log.info("Used bill splitter")
            end
            if Tool.called("calculate_discount") then
                Log.info("Used discount calculator")
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
            result = answer,
            completed = done.called()
        }
    end
}

-- BDD Specifications
Specification([[
Feature: Individual Lua Function Tools
  Demonstrate tool() function for defining individual tools

  Scenario: Calculator calculates 20% tip on $50
    Given the procedure has started
    And the agent "calculator" responds with "I've calculated the tip for you."
    And the agent "calculator" calls tool "calculate_tip" with args {"bill_amount": 50, "tip_percentage": 20}
    And the agent "calculator" calls tool "done" with args {"reason": "Bill: $50.00, Tip (20%): $10.00, Total: $60.00"}
    When the procedure runs
    Then the procedure should complete successfully
    And the output completed should be True
    And the calculate_tip tool should be called
    And the done tool should be called
    And the output result should exist
]])
