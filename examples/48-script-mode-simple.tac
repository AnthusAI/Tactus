-- Simple Script Mode Example
--
-- Demonstrates a simple procedure with input and output parameters.
-- The procedure accepts a name and returns a greeting message.

input {
        name = field.string{required = true, description = "Name to greet"}
    }

output {
        greeting = field.string{required = true, description = "Greeting message"}
    }

-- Create greeting message from input
        local message = "Hello, " .. input.name .. "!"

        return {greeting = message}

