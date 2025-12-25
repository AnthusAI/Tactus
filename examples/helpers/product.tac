-- Product Helper Procedure
-- Calculates the product of an array of numbers

procedure({
    input = {
        values = {
            type = "array",
            required = true,
            description = "Array of numbers to multiply"
        }
    },
    output = {
        result = {
            type = "number",
            required = true,
            description = "Product of all values"
        }
    },
    state = {
        total = {type = "number", default = 1}
    }
}, function()
    -- Calculate product
    for i = 1, #input.values do
        state.total = state.total * input.values[i]
    end

    return {result = state.total}
end)
