-- Sum helper procedure
-- Calculates the sum of values

Procedure {
    input = {
        values = field.array{required = true, description = "Array of numbers to sum"}
    },
    output = {
        result = field.number{required = true, description = "Sum of the values"}
    },
    function(input)
        local sum = 0
        for i, v in ipairs(input.values) do
            sum = sum + v
        end
        return {result = sum}
    end
}
