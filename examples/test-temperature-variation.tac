-- Test with high temperature to verify output variation
-- Run this multiple times - you should get different stories each time
World = Agent {
  provider = "openai",
  model = "gpt-4o-mini",
  system_prompt = "You are a creative storyteller.",
  temperature = 1.8  -- Very high for maximum variation
}

return World("Tell me a one-sentence story about a robot.")
