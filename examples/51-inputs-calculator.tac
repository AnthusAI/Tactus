-- Calculator with Array Input
-- Demonstrates array and enum input handling

procedure "main" {
    input = {
        numbers = {
            type = "array",
            required = true,
            description = "Array of numbers to calculate (e.g., [1, 2, 3, 4, 5])"
        },
        operation = {
            type = "string",
            default = "sum",
            enum = {"sum", "product", "average", "min", "max"},
            description = "Operation to perform on the numbers"
        },
        round_result = {
            type = "boolean",
            default = false,
            description = "Round the result to nearest integer"
        }
    },
    output = {
        result = {
            type = "number",
            required = true,
            description = "Calculation result"
        },
        operation_used = {
            type = "string",
            required = true,
            description = "Operation that was performed"
        },
        input_count = {
            type = "number",
            required = true,
            description = "Number of inputs processed"
        }
    },
    state = {}
,

function()
    local numbers = input.numbers
    local op = input.operation
    local result = 0
    local count = 0

    -- Count and collect numbers (Python list passed as POBJECT)
    local values = {}
    for k, n in pairs(numbers) do
        count = count + 1
        values[count] = n
    end

    if count == 0 then
        return {
            result = 0,
            operation_used = op,
            input_count = 0
        }
    end

    -- Perform calculation
    if op == "sum" then
        result = 0
        for i = 1, count do
            result = result + values[i]
        end
    elseif op == "product" then
        result = 1
        for i = 1, count do
            result = result * values[i]
        end
    elseif op == "average" then
        local total = 0
        for i = 1, count do
            total = total + values[i]
        end
        result = total / count
    elseif op == "min" then
        result = values[1]
        for i = 2, count do
            if values[i] < result then
                result = values[i]
            end
        end
    elseif op == "max" then
        result = values[1]
        for i = 2, count do
            if values[i] > result then
                result = values[i]
            end
        end
    end

    -- Round if requested
    if input.round_result then
        result = math.floor(result + 0.5)
    end

    return {
        result = result,
        operation_used = op,
        input_count = count
    }
end
}
