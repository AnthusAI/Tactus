-- Tactus Models module

local llm = require("tactus.models.llm")
local naive_bayes = require("tactus.models.naive_bayes")
local hf_transformers = require("tactus.models.hf_transformers")

return {
    LLMModel = llm.LLMModel,
    NaiveBayesModel = naive_bayes.NaiveBayesModel,
    HFTransformersModel = hf_transformers.HFTransformersModel,
}
