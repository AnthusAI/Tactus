-- Simple Script Mode Example
--
-- Demonstrates script mode without an explicit procedure() definition.
-- Top-level input and output declarations define the interface,
-- and top-level code acts as the procedure body.

input {
    name = {
        type = "string",
        required = true,
        description = "Name to greet"
    }
}

output {
    greeting = {
        type = "string",
        required = true,
        description = "Greeting message"
    }
}

-- Top-level script code (implicit main procedure)
local message = "Hello, " .. input.name .. "!"

return {greeting = message}
