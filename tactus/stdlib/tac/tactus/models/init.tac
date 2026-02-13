-- Tactus Models module

local llm = require("tactus.models.llm")
local naive_bayes = require("tactus.models.naive_bayes")
local hf_sequence_classifier = require("tactus.models.hf_sequence_classifier")

return {
    LLMModel = llm.LLMModel,
    NaiveBayesModel = naive_bayes.NaiveBayesModel,
    HFSequenceClassifierModel = hf_sequence_classifier.HFSequenceClassifierModel,
}
