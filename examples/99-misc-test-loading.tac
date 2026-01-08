-- Test loading indicators
Agent "test_agent" {
  provider = "openai",
  model = "gpt-4o-mini",
  system_prompt = "You are a helpful assistant. Respond briefly.",
}

output {
  success = field.boolean{required = true}
}

log("Starting test...")
  local result = test_agent.turn()
  log("Agent responded: " .. result.data)
  return {success = true}

