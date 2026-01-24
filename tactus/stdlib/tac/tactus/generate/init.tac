-- Tactus Generate Module
--
-- Provides flexible text generation with DSPy-inspired features:
-- - LLM-based generation (tactus.generate.llm)
-- - Optional chain-of-thought reasoning
-- - Output format control (text, JSON, markdown)
-- - Extensible base class (tactus.generate.base)
--
-- Usage:
--   local generate = require("tactus.generate")
--   local generator = generate.LLMGenerator:new{...}
--
-- Or load specific generators:
--   local LLMGenerator = require("tactus.generate.llm")

-- Load all submodules
local base = require("tactus.generate.base")
local llm = require("tactus.generate.llm")

-- Re-export all classes
return {
    -- Core classes
    BaseGenerator = base.BaseGenerator,
    LLMGenerator = llm.LLMGenerator,

    -- Helper for users who want to extend
    class = base.class,
}
