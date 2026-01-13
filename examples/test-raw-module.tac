-- Test Raw module with minimal formatting
WorldRaw = Agent {
    provider = "openai",
    model = "gpt-4o-mini",
    system_prompt = "Your name is World.",
    module = "Raw"  -- Use raw module for minimal overhead
}

return {
    WorldRaw("Hello, World!")
}
