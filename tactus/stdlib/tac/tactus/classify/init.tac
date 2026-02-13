-- Tactus Classification Module
--
-- Provides a comprehensive classification system with:
-- - LLM-based classification (tactus.classify.llm)
-- - Fuzzy string matching (tactus.classify.fuzzy)
-- - Extensible base class (tactus.classify.base)
--
-- Usage:
--   local classify = require("tactus.classify")
--   local classifier = classify.LLMClassifier:new{...}
--
-- Or load specific classifiers:
--   local LLMClassifier = require("tactus.classify.llm")
--
-- Or use the Classify factory (same API as the global):
--   local classify = require("tactus.classify")
--   local result = classify.Classify {
--       classes = {"Yes", "No"},
--       prompt = "Is this a question?",
--       input = "How are you?"
--   }

-- Load all submodules
local base = require("tactus.classify.base")
local llm = require("tactus.classify.llm")
local fuzzy = require("tactus.classify.fuzzy")
local naive_bayes = require("tactus.classify.naive_bayes")

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
