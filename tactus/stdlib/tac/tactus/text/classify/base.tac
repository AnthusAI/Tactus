-- Base Classification Class
--
-- This module provides the foundation for all classifiers:
-- - class() helper for Lua OOP with inheritance
-- - BaseClassifier abstract base class

-- Simple class system for Lua
local function class(base)
    local c = {}
    if base then
        for k, v in pairs(base) do
            c[k] = v
        end
        c._base = base
    end
    c.__index = c

    function c:new(config)
        local instance = setmetatable({}, self)
        if instance.init then
            instance:init(config)
        end
        return instance
    end

    return c
end

-- ============================================================================
-- BaseClassifier (Abstract Base Class)
-- ============================================================================

local BaseClassifier = class()

function BaseClassifier:init(config)
    self.config = config or {}
end

function BaseClassifier:classify(text)
    error("BaseClassifier.classify() must be implemented by subclass")
end

function BaseClassifier:__call(text)
    return self:classify(text)
end

-- Export classes and helpers
return {
    class = class,
    BaseClassifier = BaseClassifier,
}
