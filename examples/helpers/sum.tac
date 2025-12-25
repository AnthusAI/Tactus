-- Sum Helper Procedure
-- Calculates the sum of an array of numbers

procedure({
    input = {
        values = {
            type = "array",
            required = true,
            description = "Array of numbers to sum"
        }
    },
    output = {
        result = {
            type = "number",
            required = true,
            description = "Sum of all values"
        }
    },
    state = {
        total = {type = "number", default = 0}
    }
}, function()
    -- Calculate sum
    for i = 1, #input.values do
        state.total = state.total + input.values[i]
    end

    return {result = state.total}
end)
