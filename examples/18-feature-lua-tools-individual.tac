--[[
Example: Individual Lua Function Tools

Demonstrates defining tools using the tool() function.
Each tool() declaration creates a single-tool toolset that can be
referenced by name in agent configurations.

To run this example:
tactus run examples/18-feature-lua-tools-individual.tac --param task="Calculate 15% tip on a $50 bill"
]]--

-- Define individual tools using the tool() function
tool("calculate_tip", {
    description = "Calculate tip amount for a bill",
    parameters = {
        bill_amount = {
            type = "number",
            description = "Total bill amount in dollars",
            required = true
        },
        tip_percentage = {
            type = "number",
            description = "Tip percentage (e.g., 15 for 15%)",
            required = true
        }
    }
}, function(args)
    local tip = args.bill_amount * (args.tip_percentage / 100)
    local total = args.bill_amount + tip
    return string.format("Bill: $%.2f, Tip (%.0f%%): $%.2f, Total: $%.2f",
        args.bill_amount, args.tip_percentage, tip, total)
end)

tool("split_bill", {
    description = "Split a bill total among multiple people",
    parameters = {
        total_amount = {
            type = "number",
            description = "Total amount to split",
            required = true
        },
        num_people = {
            type = "integer",
            description = "Number of people to split among",
            required = true
        }
    }
}, function(args)
    local per_person = args.total_amount / args.num_people
    return string.format("Split $%.2f among %d people = $%.2f per person",
        args.total_amount, args.num_people, per_person)
end)

tool("calculate_discount", {
    description = "Calculate price after discount",
    parameters = {
        original_price = {
            type = "number",
            description = "Original price",
            required = true
        },
        discount_percent = {
            type = "number",
            description = "Discount percentage",
            required = true
        }
    }
}, function(args)
    local discount_amount = args.original_price * (args.discount_percent / 100)
    local final_price = args.original_price - discount_amount
    return string.format("Original: $%.2f, Discount (%.0f%%): $%.2f, Final: $%.2f",
        args.original_price, args.discount_percent, discount_amount, final_price)
end)

-- Agent with access to individual Lua tools
agent("calculator", {
    provider = "openai",
    model = "gpt-4o-mini",
    tool_choice = "required",
    system_prompt = [[You are a helpful calculator assistant.

IMPORTANT: You MUST call the appropriate tool for EVERY calculation. Never calculate directly.

After calling the calculation tool, call done with the result.]],
    initial_message = "{input.task}",
    toolsets = {
        -- Reference individual tools by name
        "calculate_tip",
        "split_bill",
        "calculate_discount",
        "done"
    }
})

-- Main workflow
main = procedure("main", {
    input = {
        task = {
            type = "string",
            default = "Calculate 20% tip on $50",
            description = "Calculation task to perform"
        }
    },
    output = {
        result = {
            type = "string",
            required = true,
            description = "The calculation result"
        },
        completed = {
            type = "boolean",
            required = true,
            description = "Whether the task was completed successfully"
        }
    },
    state = {}
}, function()
    local max_turns = 5
    local turn_count = 0
    local result

    repeat
        result = Calculator.turn()
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

    until Tool.called("done") or turn_count >= max_turns

    -- Get final result
    local answer
    if Tool.called("done") then
        answer = Tool.last_call("done").args.reason
    else
        answer = result.text
    end

    return {
        result = answer,
        completed = Tool.called("done")
    }
end)

-- BDD Specifications
specifications([[
Feature: Individual Lua Function Tools
  Demonstrate tool() function for defining individual tools

  Scenario: Calculator calculates 20% tip on $50
    Given the procedure has started
    When the procedure runs
    Then the procedure should complete successfully
    And the output completed should be True
    And the calculate_tip tool should be called
    And the calculate_tip tool should be called with bill_amount=50
    And the calculate_tip tool should be called with tip_percentage=20
    And the output result should be similar to "$10.00"
]])
