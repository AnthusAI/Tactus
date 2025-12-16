-- Test loading indicators
agent("test_agent", {
  provider = "openai",
  model = "gpt-4o-mini",
  system_prompt = "You are a helpful assistant. Respond briefly.",
})

procedure(function()
  log("Starting test...")
  local result = test_agent.turn()
  log("Agent responded: " .. result.data)
  return {success = true}
end)
