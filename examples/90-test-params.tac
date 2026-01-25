-- Test if parameter passing is the issue
print("Test: parameters")

function main(input)
    print("IN MAIN! input type: " .. type(input))
    if input then
        print("Input is not nil")
        for k, v in pairs(input) do
            print("  " .. k .. " = " .. tostring(v))
        end
    else
        print("Input is nil")
    end
    return {test = "success"}
end

print("Defined main")
