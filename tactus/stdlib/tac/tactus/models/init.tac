-- Tactus Models module

local llm = require("tactus.models.llm")
local naive_bayes = require("tactus.models.naive_bayes")

return {
    LLMModel = llm.LLMModel,
    NaiveBayesModel = naive_bayes.NaiveBayesModel,
}
