-- Sum Helper Procedure
-- Calculates the sum of an array of numbers

Procedure "main" {
    input = {
        values = field.array{required = true, description = "Array of numbers to sum"}
    },
    output = {
        result = field.number{required = true, description = "Sum of all values"}
    },
    state = {
        total = field.number{default = 0}
    },
    function(input)
    -- Calculate sum
    for i = 1, #input.values do
        State.total = State.total + input.values[i]
    end

    return {result = State.total}
end
}
