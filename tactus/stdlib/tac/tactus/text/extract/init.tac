-- Tactus Extraction Module
--
-- Provides structured data extraction from text with:
-- - LLM-based extraction (tactus.text.extract.llm)
-- - Field validation and type coercion
-- - Extensible base class (tactus.text.extract.base)
--
-- Usage:
--   local extract = require("tactus.text.extract")
--   local extractor = extract.LLMExtractor:new{...}
--
-- Or load specific extractors:
--   local LLMExtractor = require("tactus.text.extract.llm")

-- Load all submodules
local base = require("tactus.text.extract.base")
local llm = require("tactus.text.extract.llm")

-- Re-export all classes
return {
    -- Core classes
    BaseExtractor = base.BaseExtractor,
    LLMExtractor = llm.LLMExtractor,

    -- Helper for users who want to extend
    class = base.class,
}
