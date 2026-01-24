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

-- Load all submodules
local base = require("tactus.classify.base")
local llm = require("tactus.classify.llm")
local fuzzy = require("tactus.classify.fuzzy")

-- Re-export all classes
return {
    -- Core classes
    BaseClassifier = base.BaseClassifier,
    LLMClassifier = llm.LLMClassifier,
    FuzzyMatchClassifier = fuzzy.FuzzyMatchClassifier,

    -- Helper for users who want to extend
    class = base.class,
}
