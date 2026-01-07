-- Product Helper Procedure
-- Calculates the product of an array of numbers

Procedure "main" {
    input = {
        values = field.array{required = true, description = "Array of numbers to multiply"}
    },
    output = {
        result = field.number{required = true, description = "Product of all values"}
    },
    state = {
        total = field.number{default = 1}
    },
    function(input)
    -- Calculate product
    for i = 1, #input.values do
        State.total = State.total * input.values[i]
    end

    return {result = State.total}
end
}
