-- Naive Bayes Model helper built on the Model primitive (registry-backed).
--
-- Usage:
--   local models = require("tactus.models.naive_bayes")
--   local imdb = models.NaiveBayesModel{
--       name = "imdb_nb",
--       version = "latest"
--   }
--   local result = imdb({text = "great movie"})

local function NaiveBayesModel(config)
    assert(config.name, "NaiveBayesModel requires 'name'")
    local version = config.version or "latest"

    return Model (config.name) {
        type = "registry",
        name = config.name,
        version = version,
        input = { text = "string" },
        output = { label = "string", confidence = "float" },
    }
end

return {
    NaiveBayesModel = NaiveBayesModel,
}
