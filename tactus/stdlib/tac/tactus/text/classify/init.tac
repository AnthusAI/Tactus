-- Tactus Classification Module
--
-- Provides a comprehensive classification system with:
-- - LLM-based classification (tactus.text.classify.llm)
-- - Fuzzy string matching (tactus.text.classify.fuzzy)
-- - Extensible base class (tactus.text.classify.base)
--
-- Usage:
--   local classify = require("tactus.text.classify")
--   local classifier = classify.LLMClassifier:new{...}
--
-- Or load specific classifiers:
--   local LLMClassifier = require("tactus.text.classify.llm")
--
-- Or use the Classify factory (same API as the global):
--   local classify = require("tactus.text.classify")
--   local result = classify.Classify {
--       classes = {"Yes", "No"},
--       prompt = "Is this a question?",
--       input = "How are you?"
--   }

-- Load all submodules
local base = require("tactus.text.classify.base")
local llm = require("tactus.text.classify.llm")
local fuzzy = require("tactus.text.classify.fuzzy")
local naive_bayes = require("tactus.text.classify.naive_bayes")

-- Classify factory: dispatches to the right classifier based on config
local function Classify(config)
    local method = config.method or "llm"
    local classifier

    if method == "fuzzy" then
        classifier = fuzzy.FuzzyMatchClassifier:new(config)
    elseif method == "naive_bayes" then
        classifier = naive_bayes.NaiveBayesClassifier:new(config)
    else
        classifier = llm.LLMClassifier:new(config)
    end

    if config.input then
        return classifier:classify(config.input)
    else
        return classifier
    end
end

-- Re-export all classes and the factory
return {
    -- Core classes
    BaseClassifier = base.BaseClassifier,
    LLMClassifier = llm.LLMClassifier,
    FuzzyMatchClassifier = fuzzy.FuzzyMatchClassifier,
    NaiveBayesClassifier = naive_bayes.NaiveBayesClassifier,

    -- Factory
    Classify = Classify,

    -- Helper for users who want to extend
    class = base.class,
}
