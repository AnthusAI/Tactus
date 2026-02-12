-- Fuzzy String Matching Classification
--
-- Provides string similarity-based classification using rapidfuzz (via Python):
-- - Binary mode: match against a single expected value (Yes/No)
-- - Multi-class mode: find best match from a list of classes
-- - Multiple algorithms: ratio, token_set_ratio, token_sort_ratio, partial_ratio
-- - Configurable similarity threshold

-- Load dependencies
local base = require("tactus.classify.base")
local BaseClassifier = base.BaseClassifier
local class = base.class

-- Load Python similarity helper (rapidfuzz backend)
local similarity = require("tactus.classify.similarity")

-- ============================================================================
-- FuzzyMatchClassifier
-- ============================================================================

local FuzzyMatchClassifier = class(BaseClassifier)

function FuzzyMatchClassifier:init(config)
    BaseClassifier.init(self, config)

    self.threshold = config.threshold or 0.8
    self.algorithm = config.algorithm or "ratio"

    if config.expected then
        -- Binary mode: Yes/No based on match to expected value
        self.mode = "binary"
        self.expected = config.expected
        self.classes = config.classes or {"Yes", "No"}
    elseif config.classes then
        -- Multi-class mode: return closest matching class
        self.mode = "multiclass"
        self.classes = config.classes
    else
        error("FuzzyMatchClassifier requires either 'expected' (binary mode) or 'classes' (multi-class mode)")
    end
end

function FuzzyMatchClassifier:classify(input_text)
    if self.mode == "binary" then
        return self:classify_binary(input_text)
    else
        return self:classify_multiclass(input_text)
    end
end

function FuzzyMatchClassifier:classify_binary(input_text)
    local score = similarity.calculate_similarity(
        input_text, self.expected, self.algorithm
    )

    if score >= self.threshold then
        return {
            value = self.classes[1],  -- "Yes"
            confidence = score,
            matched_text = self.expected,
            retry_count = 0,
        }
    else
        return {
            value = self.classes[2],  -- "No"
            confidence = 1.0 - score,
            matched_text = nil,
            retry_count = 0,
        }
    end
end

function FuzzyMatchClassifier:classify_multiclass(input_text)
    local best_match = nil
    local best_score = 0.0

    for _, cls in ipairs(self.classes) do
        local score = similarity.calculate_similarity(
            input_text, cls, self.algorithm
        )
        if score > best_score then
            best_score = score
            best_match = cls
        end
    end

    if best_score >= self.threshold then
        return {
            value = best_match,
            confidence = best_score,
            matched_text = best_match,
            retry_count = 0,
        }
    else
        return {
            value = "NO_MATCH",
            confidence = 1.0 - best_score,
            matched_text = nil,
            retry_count = 0,
        }
    end
end

-- Export FuzzyMatchClassifier
return {
    FuzzyMatchClassifier = FuzzyMatchClassifier,
}
