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

local function build_system_prompt(config)
    assert(config.prompt, "LLMModel requires 'prompt'")
    assert(config.classes, "LLMModel requires 'classes'")
    local classes_str = table.concat(config.classes, ", ")

    return string.format([[%s

You MUST respond in JSON:
{"value": "<one of: %s>", "confidence": <0-1 number>, "explanation": "<brief reasoning>"}

Valid values: %s
Only one classification is allowed.]],
        config.prompt,
        classes_str,
        classes_str
    )
end

local function LLMModel(config)
    local system_prompt = config.system_prompt or build_system_prompt(config)
    local retries = config.retries or config.max_retries or 3
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
        retries = retries,
        parse_direction = config.parse_direction or "end",
        max_tokens = config.max_tokens,
        input = { text = "string" },
        output = { value = "string", confidence = "float", explanation = "string" },
    }
end

return {
    LLMModel = LLMModel,
}
