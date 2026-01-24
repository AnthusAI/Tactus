-- Fuzzy String Matching Classification
--
-- Provides string similarity-based classification:
-- - Configurable similarity threshold
-- - Case-insensitive matching
-- - Character overlap similarity algorithm

-- Load dependencies
local base = require("tactus.classify.base")
local BaseClassifier = base.BaseClassifier
local class = base.class

-- ============================================================================
-- FuzzyMatchClassifier
-- ============================================================================

local FuzzyMatchClassifier = class(BaseClassifier)

function FuzzyMatchClassifier:init(config)
    BaseClassifier.init(self, config)

    assert(config.expected, "FuzzyMatchClassifier requires 'expected' field")

    self.expected = config.expected
    self.threshold = config.threshold or 0.8
    self.classes = config.classes or {"Yes", "No"}
end

function FuzzyMatchClassifier:calculate_similarity(s1, s2)
    s1 = s1:lower()
    s2 = s2:lower()

    if s1 == s2 then
        return 1.0
    end

    if s1:find(s2, 1, true) or s2:find(s1, 1, true) then
        return 0.85
    end

    -- Character overlap similarity
    local set1 = {}
    for i = 1, #s1 do
        set1[s1:sub(i,i)] = true
    end

    local intersection = 0
    local set2 = {}
    for i = 1, #s2 do
        local char = s2:sub(i,i)
        set2[char] = true
        if set1[char] then
            intersection = intersection + 1
        end
    end

    local union = 0
    for _ in pairs(set1) do union = union + 1 end
    for char in pairs(set2) do
        if not set1[char] then
            union = union + 1
        end
    end

    if union == 0 then
        return 0.0
    end

    return intersection / union
end

function FuzzyMatchClassifier:classify(input_text)
    local similarity = self:calculate_similarity(input_text, self.expected)
    local value = similarity >= self.threshold and self.classes[1] or self.classes[2]

    return {
        value = value,
        confidence = similarity,
        matched_text = self.expected,  -- What it matched against
        retry_count = 0
    }
end

-- Export FuzzyMatchClassifier
return {
    FuzzyMatchClassifier = FuzzyMatchClassifier,
}
