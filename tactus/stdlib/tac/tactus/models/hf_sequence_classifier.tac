-- Hugging Face sequence classifier helper built on the Model primitive.
--
-- Usage:
--   local models = require("tactus.models.hf_sequence_classifier")
--   local classifier = models.HFSequenceClassifierModel{
--       name = "imdb_classifier",
--       model = "distilbert-base-uncased-finetuned-sst-2-english"
--   }
--   local result = classifier({text = "great movie"})

local function HFSequenceClassifierModel(config)
    assert(config.model, "HFSequenceClassifierModel requires 'model'")
    return Model (config.name or "hf_sequence_classifier") {
        type = "hf_sequence_classifier",
        model = config.model,
        revision = config.revision,
        device = config.device,
        input = { text = "string" },
        output = { label = "string", confidence = "float" },
    }
end

return {
    HFSequenceClassifierModel = HFSequenceClassifierModel,
}
