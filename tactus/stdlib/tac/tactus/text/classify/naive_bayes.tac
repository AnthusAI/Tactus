-- Naive Bayes Classification (registry-backed).

local base = require("tactus.text.classify.base")
local BaseClassifier = base.BaseClassifier
local class = base.class
local models = require("tactus.models.naive_bayes")

local NaiveBayesClassifier = class(BaseClassifier)

function NaiveBayesClassifier:init(config)
    BaseClassifier.init(self, config)
    assert(config.name, "NaiveBayesClassifier requires 'name'")
    self.name = config.name
    self.version = config.version or "latest"

    self.model = models.NaiveBayesModel {
        name = self.name,
        version = self.version,
    }
end

function NaiveBayesClassifier:classify(input_text)
    local result = self.model({text = input_text})
    local output = result
    local ok, maybe_output = pcall(function()
        return result["output"]
    end)
    if ok and maybe_output ~= nil then
        output = maybe_output
    elseif type(result) == "table" and result.output ~= nil then
        output = result.output
    end

    local function safe_get(obj, key)
        if obj == nil then
            return nil
        end
        if type(obj) == "table" then
            return obj[key]
        end
        local ok_get, val = pcall(function()
            return obj[key]
        end)
        if ok_get then
            return val
        end
        return nil
    end

    return {
        value = safe_get(output, "label"),
        confidence = safe_get(output, "confidence"),
        raw_response = output,
    }
end

return {
    NaiveBayesClassifier = NaiveBayesClassifier,
}
