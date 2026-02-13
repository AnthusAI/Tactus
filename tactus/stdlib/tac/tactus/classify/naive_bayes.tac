-- Naive Bayes Classification (registry-backed).

local base = require("tactus.classify.base")
local BaseClassifier = base.BaseClassifier
local class = base.class
local models = require("tactus.models.naive_bayes")

local NaiveBayesClassifier = class(BaseClassifier)

function NaiveBayesClassifier:init(config)
    BaseClassifier.init(self, config)
    assert(config.name, "NaiveBayesClassifier requires 'name'")
    self.name = config.name
    self.version = config.version or "latest"

    self.model = models.NaiveBayesModel {
        name = self.name,
        version = self.version,
    }
end

function NaiveBayesClassifier:classify(input_text)
    local result = self.model({text = input_text})
    local output = result.output or result

    return {
        value = output.label,
        confidence = output.confidence,
        raw_response = output,
    }
end

return {
    NaiveBayesClassifier = NaiveBayesClassifier,
}
