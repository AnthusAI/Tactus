-- HuggingFace AutoModel helper built on the Model primitive.
--
-- Usage:
--   local models = require("tactus.models.hf_transformers")
--   local bert = models.HFTransformersModel{
--       name = "bert_imdb",
--       model = "distilbert-base-uncased-finetuned-sst-2-english"
--   }
--   local result = bert({text = "great movie"})

local function HFTransformersModel(config)
    assert(config.model, "HFTransformersModel requires 'model'")
    return Model (config.name or "hf_transformers") {
        type = "hf_transformers",
        model = config.model,
        revision = config.revision,
        device = config.device,
        input = { text = "string" },
        output = { label = "string", confidence = "float" },
    }
end

return {
    HFTransformersModel = HFTransformersModel,
}
