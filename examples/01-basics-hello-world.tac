World = Agent {
    provider = "openai",
    model = "gpt-4o-mini",
    system_prompt = "Your name is World.",
    module = "Raw"  -- No DSPy delimiter formatting
}

Procedure {
    output = {
        message = field.string{required = true}
    },
    function(_)
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
