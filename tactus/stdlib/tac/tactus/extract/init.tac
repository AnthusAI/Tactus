-- Tactus Extraction Module
--
-- Provides structured data extraction from text with:
-- - LLM-based extraction (tactus.extract.llm)
-- - Field validation and type coercion
-- - Extensible base class (tactus.extract.base)
--
-- Usage:
--   local extract = require("tactus.extract")
--   local extractor = extract.LLMExtractor:new{...}
--
-- Or load specific extractors:
--   local LLMExtractor = require("tactus.extract.llm")

-- Load all submodules
local base = require("tactus.extract.base")
local llm = require("tactus.extract.llm")

-- Re-export all classes
return {
    -- Core classes
    BaseExtractor = base.BaseExtractor,
    LLMExtractor = llm.LLMExtractor,

    -- Helper for users who want to extend
    class = base.class,
}
