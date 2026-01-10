World = Agent {
    provider = "openai",
    model = "gpt-4o-mini",
    system_message = "Your name is World."
}

return World("Hello, World!").response
