-- Simple Script Mode Example
--
-- Demonstrates a simple procedure with input and output parameters.
-- The procedure accepts a name and returns a greeting message.

Procedure {
    input = {
            name = field.string{required = true, description = "Name to greet"}
    },
    output = {
            greeting = field.string{required = true, description = "Greeting message"}
    },
    function(input)

    -- Create greeting message from input
            local message = "Hello, " .. input.name .. "!"

            return {greeting = message}

    end
}