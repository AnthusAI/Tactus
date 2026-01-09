--[[
Math Tools Module

This module provides math operation tool definitions that can be imported via require().
Usage: local math_tools = require("examples/helpers/math_module")

Note: Returns raw tool definitions (tables), not Tool objects.
These should be used with a type="lua" Toolset in the main file.
]]--

local M = {}

M.add = {
    name = "add",
    description = "Add two numbers together",
    input = {
        a = field.number{required = true, description = "First number"},
        b = field.number{required = true, description = "Second number"}
    },
    handler = function(args)
        local result = args.a + args.b
        return string.format("%g + %g = %g", args.a, args.b, result)
    end
}

M.multiply = {
    name = "multiply",
    description = "Multiply two numbers",
    input = {
        a = field.number{required = true, description = "First number"},
        b = field.number{required = true, description = "Second number"}
    },
    handler = function(args)
        local result = args.a * args.b
        return string.format("%g * %g = %g", args.a, args.b, result)
    end
}

return M
