World = Agent {
    provider = "openai",
    model = "gpt-4o-mini",
    system_prompt = "Your name is World.",
    module = "Raw"  -- No DSPy delimiter formatting
}

return World("Hello, World!")