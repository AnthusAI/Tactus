-- Test with high temperature, multiple calls to same agent
-- This demonstrates that high temperature produces varied outputs
-- even with identical prompts

Storyteller = Agent {
  provider = "openai",
  model = "gpt-4o-mini",
  system_prompt = "You are a creative storyteller.",
  temperature = 1.8  -- Very high for maximum variation
}

Procedure {
  function(input)
    local prompt = "Tell me a one-sentence story about a robot."

    print("Running the same prompt 5 times with temperature=1.8")
    print("Expected: Different stories each time")
    print("=" .. string.rep("=", 60))

    for i = 1, 5 do
      print("\n[Story " .. i .. "]")
      local response = Storyteller(prompt)
      print(response)
    end

    print("\n" .. string.rep("=", 60))
    print("All stories generated!")

    return {
      message = "Generated 5 different robot stories with high temperature",
      complete = true
    }
  end
}
