-- Base Extraction Class
--
-- This module provides the foundation for all extractors:
-- - class() helper for Lua OOP with inheritance
-- - BaseExtractor abstract base class

-- Simple class system for Lua (shared with classify module pattern)
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
-- BaseExtractor (Abstract Base Class)
-- ============================================================================

local BaseExtractor = class()

function BaseExtractor:init(config)
    self.config = config or {}
    self.fields = config.fields or {}
    self.prompt = config.prompt or ""
    self.strict = config.strict ~= false  -- Default to strict mode
    self.max_retries = config.max_retries or 3
end

function BaseExtractor:extract(text)
    error("BaseExtractor.extract() must be implemented by subclass")
end

function BaseExtractor:__call(text)
    return self:extract(text)
end

-- Helper to validate extracted fields against schema
function BaseExtractor:validate_fields(extracted, schema)
    local errors = {}
    local result = {}

    for field_name, field_type in pairs(schema) do
        local value = extracted[field_name]

        if value == nil then
            if self.strict then
                table.insert(errors, "Missing required field: " .. field_name)
            end
            result[field_name] = nil
        else
            local validated, err = self:validate_field(field_name, value, field_type)
            if err then
                table.insert(errors, err)
            end
            result[field_name] = validated
        end
    end

    return result, errors
end

-- Validate a single field value against its type
function BaseExtractor:validate_field(field_name, value, field_type)
    if value == nil then
        return nil, nil
    end

    local type_lower = string.lower(field_type)

    if type_lower == "string" then
        return tostring(value), nil

    elseif type_lower == "number" then
        local num = tonumber(value)
        if num then
            return num, nil
        end
        return nil, "Field '" .. field_name .. "' must be a number"

    elseif type_lower == "integer" then
        local num = tonumber(value)
        if num then
            return math.floor(num), nil
        end
        return nil, "Field '" .. field_name .. "' must be an integer"

    elseif type_lower == "boolean" then
        if type(value) == "boolean" then
            return value, nil
        end
        if type(value) == "string" then
            local lower = string.lower(value)
            if lower == "true" or lower == "yes" or lower == "1" then
                return true, nil
            end
            if lower == "false" or lower == "no" or lower == "0" then
                return false, nil
            end
        end
        return nil, "Field '" .. field_name .. "' must be a boolean"

    elseif type_lower == "list" or type_lower == "array" then
        if type(value) == "table" then
            return value, nil
        end
        return nil, "Field '" .. field_name .. "' must be a list"

    elseif type_lower == "object" or type_lower == "dict" then
        if type(value) == "table" then
            return value, nil
        end
        return nil, "Field '" .. field_name .. "' must be an object"

    else
        -- Unknown type, accept any value
        return value, nil
    end
end

-- Export classes and helpers
return {
    class = class,
    BaseExtractor = BaseExtractor,
}
