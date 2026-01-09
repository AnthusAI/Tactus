-- Product helper procedure
-- Calculates the product of values

Procedure {
    input = {
        values = field.array{required = true, description = "Array of numbers to multiply"}
    },
    output = {
        result = field.number{required = true, description = "Product of the values"}
    },
    function(input)
        local product = 1
        for i, v in ipairs(input.values) do
            product = product * v
        end
        return {result = product}
    end
}
