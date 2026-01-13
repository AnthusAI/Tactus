-- Test loading indicators
test_agent = Agent {
  provider = "openai",
  model = "gpt-4o-mini",
  system_prompt = "You are a helpful assistant. Respond briefly.",
}

Procedure {
    output = {
      success = field.boolean{required = true}
    },
    function(input)

    log("Starting test...")
      local result = test_agent()
      log("Agent responded: " .. result.data)
      return {success = true}

    end
}