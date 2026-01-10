World = Agent {
    provider = "openai",
    model = "gpt-4o-mini",
    system_prompt = "Your name is World."
}

return {
    World("Hello, World!")
}
