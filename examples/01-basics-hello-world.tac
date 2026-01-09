World = Agent {
    provider = "openai",
    model = "gpt-4o-mini",
    system_prompt = "Your name is World."
}

return {
    message = (World {message = "Hello, World!"}).response
}
