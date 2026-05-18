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

-- Counter for unique model names, preventing registry collisions when LLMModel
-- is called multiple times (e.g., in a loop) with the same base name.
local _llm_model_counter = 0

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

    -- Append a unique counter suffix to avoid registry lookup collisions.
    -- Without this, Model("llm_classifier") on the 2nd+ call returns the existing
    -- handle and tries to run inference with the config table as input (wrong path).
    _llm_model_counter = _llm_model_counter + 1
    local unique_name = (config.name or "llm_model") .. "_" .. _llm_model_counter

    return Model (unique_name) {
        type = "llm",
        model = model,
        provider = provider,
        system_prompt = system_prompt,
        temperature = temperature,
        max_tokens = config.max_tokens,
        reasoning_effort = config.reasoning_effort,
        verbosity = config.verbosity,
        input = { text = "string" },
        output = { response = "string" },
    }
end

return {
    LLMModel = LLMModel,
}
