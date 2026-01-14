World = Agent {
    provider = "openai",
    model = "gpt-4o-mini",
    system_prompt = "Your name is World."
}

-- Mock for CI/BDD testing
Mocks {
    World = {
        tool_calls = {},
        message = "Hello! I'm World, nice to meet you!"
    }
}

return World({message = "Hello, World!"})
