-- Example: Model-based classification with the LLM Model primitive.

local models = require("tactus.models")

local sentiment = models.LLMModel{
  name = "sentiment",
  classes = {"positive", "negative"},
  prompt = "Classify sentiment as positive or negative.",
  model = "openai/gpt-4o-mini",
  temperature = 0.0
}

Procedure "main" {
  input = {
    text = field.string{default = "Great movie!"}
  },
  output = {
    label = field.string{},
    confidence = field.number{}
  },
  state = {},
  function(input)
    if os.getenv("TACTUS_MOCK_MODE") == "1" then
      return {label = "positive", confidence = 1.0}
    end

    local result = sentiment({text = input.text})
    local output = result.output or result
    return {
      label = output.value or output.label or "unknown",
      confidence = output.confidence or 0.0
    }
  end
}
