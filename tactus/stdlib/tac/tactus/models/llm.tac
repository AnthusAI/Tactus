-- LLM Model helper built on the Model primitive.
--
-- Usage:
--   local models = require("tactus.models.llm")
--   local sentiment = models.LLMModel{
--       name = "sentiment",
--       classes = {"positive", "negative", "neutral"},
--       prompt = "Classify sentiment",
--       model = "openai/gpt-4o-mini",
--       temperature = 0.0,
--   }
--   local result = sentiment({text = "great!"})
--

local function LLMModel(config)
    assert(config.prompt, "LLMModel requires 'prompt'")
    local system_prompt = config.system_prompt or config.prompt
    local temperature = config.temperature

    -- Derive provider/model if given as "provider/model"
    local provider = config.provider
    local model = config.model
    if not provider and model then
        local p, m = model:match("([^/]+)/(.+)")
        if p and m then
            provider = p
            model = p .. "/" .. m
        end
    end

    return Model (config.name or "llm_model") {
        type = "llm",
        model = model,
        provider = provider,
        system_prompt = system_prompt,
        temperature = temperature,
        max_tokens = config.max_tokens,
        input = { text = "string" },
        output = { response = "string" },
    }
end

return {
    LLMModel = LLMModel,
}
