-- Test Raw module streaming
Story = Agent {
    provider = "openai",
    model = "gpt-4o-mini",
    system_prompt = "You are a storyteller.",
    module = "Raw"  -- Use raw module for minimal overhead
}

return {
    Story("Tell me a very short story about a robot.")
}
