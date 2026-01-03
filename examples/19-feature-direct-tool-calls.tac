--[[
Example: Direct Tool Calls

Demonstrates calling tools directly from Lua code without agent involvement,
and passing tool results to agents via the context parameter.

Key Features:
- tool() returns a callable handle (OOP style)
- Syntax: tool("name", {config}, function) - consistent with agent/procedure
- Call tools directly: result = my_tool({args})
- Pass multiple tool results to agents via context
- Deterministic control over tool execution

To run this example:
tactus run examples/19-feature-direct-tool-calls.tac --param bill=100 --param tip_pct=20 --param people=4
]]--

-- tool() returns a callable - syntax matches agent() and procedure()
local calculate_tip = tool("calculate_tip", {
    description = "Calculate tip amount for a bill",
    parameters = {
        bill_amount = {type = "number", required = true, description = "Total bill amount"},
        tip_percentage = {type = "number", required = true, description = "Tip percentage"}
    }
}, function(args)
    local tip = args.bill_amount * (args.tip_percentage / 100)
    local total = args.bill_amount + tip
    return string.format("Bill: $%.2f, Tip (%.0f%%): $%.2f, Total: $%.2f",
        args.bill_amount, args.tip_percentage, tip, total)
end)

local split_bill = tool("split_bill", {
    description = "Split a bill total among multiple people",
    parameters = {
        total_amount = {type = "number", required = true, description = "Total to split"},
        num_people = {type = "integer", required = true, description = "Number of people"}
    }
}, function(args)
    local per_person = args.total_amount / args.num_people
    return string.format("Split $%.2f among %d people = $%.2f per person",
        args.total_amount, args.num_people, per_person)
end)

-- Define completion tool
tool("done", {
    description = "Signal completion of the task",
    parameters = {
        reason = {type = "string", required = true, description = "Completion message"}
    }
}, function(args)
    return "Done: " .. args.reason
end)

-- Agent for summarizing (only has done tool - doesn't need calculation tools)
agent("summarizer", {
    provider = "openai",
    model = "gpt-4o-mini",
    system_prompt = [[You are a helpful assistant that summarizes calculation results.

Given the calculation results in the context, provide a brief, friendly summary
that explains what was calculated and the final amounts.

After summarizing, call the 'done' tool with your summary as the reason.]],
    toolsets = {"done"}
})

-- Main procedure with DETERMINISTIC tool calls
main = procedure("main", {
    input = {
        bill = {type = "number", default = 100, description = "Original bill amount"},
        tip_pct = {type = "number", default = 20, description = "Tip percentage"},
        people = {type = "integer", default = 4, description = "Number of people splitting"}
    },
    output = {
        tip_result = {type = "string", required = true, description = "Tip calculation result"},
        split_result = {type = "string", required = true, description = "Bill split result"},
        summary = {type = "string", required = true, description = "Agent summary"}
    }
}, function()
    Log.info("Starting direct tool call example...")

    -- Call tools DIRECTLY - deterministic, no LLM involvement!
    Log.info("Calculating tip...")
    local tip_result = calculate_tip({
        bill_amount = input.bill,
        tip_percentage = input.tip_pct
    })
    Log.info("Tip calculated: " .. tip_result)

    -- Calculate total with tip for splitting
    local total_with_tip = input.bill * (1 + input.tip_pct / 100)

    Log.info("Splitting bill...")
    local split_result = split_bill({
        total_amount = total_with_tip,
        num_people = input.people
    })
    Log.info("Split calculated: " .. split_result)

    -- Pass multiple tool results to agent via context
    -- This is more efficient than having the agent call tools itself
    Log.info("Asking agent to summarize results...")
    Summarizer.turn({
        context = {
            tip_calculation = tip_result,
            split_calculation = split_result,
            original_bill = "$" .. input.bill,
            number_of_people = input.people
        }
    })

    -- Wait for agent to call done
    local max_turns = 3
    local turn_count = 1
    while not Tool.called("done") and turn_count < max_turns do
        Summarizer.turn()
        turn_count = turn_count + 1
    end

    -- Get the summary
    local summary = "No summary provided"
    if Tool.called("done") then
        summary = Tool.last_call("done").args.reason
    end

    return {
        tip_result = tip_result,
        split_result = split_result,
        summary = summary
    }
end)

-- BDD Specifications
specifications([[
Feature: Direct Tool Calls
  Demonstrate calling tools directly from Lua without agent involvement

  Scenario: Calculate tip and split bill for a group
    Given the procedure has started
    When the procedure runs
    Then the procedure should complete successfully
    And the calculate_tip tool should be called
    And the split_bill tool should be called
    And the output tip_result should contain "Tip"
    And the output split_result should contain "per person"
    And the output summary should not be empty
]])
