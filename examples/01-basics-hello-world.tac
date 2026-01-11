World = Agent {
    provider = "openai",
    model = "gpt-4o-mini",
    system_prompt = "Your name is World."
}

Procedure {
    output = {
        message = field.string{required = true}
    },
    function(input)
        local result = World({message = "Hello, World!"})
        return {message = result.response}
    end
}

Mocks {
    World = {
        tool_calls = {},
        message = "Hello, World!"
    }
}
