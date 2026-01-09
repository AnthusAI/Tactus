--[[
String Tools Module

This module provides string manipulation tool definitions that can be imported via require().
Usage: local string_tools = require("examples/helpers/string_module")

Note: Returns raw tool definitions (tables), not Tool objects.
These should be used with a type="lua" Toolset in the main file.
]]--

local M = {}

M.uppercase = {
    name = "uppercase",
    description = "Convert text to uppercase",
    input = {
        text = field.string{required = true, description = "Text to convert"}
    },
    handler = function(args)
        return args.text:upper()
    end
}

M.reverse = {
    name = "reverse",
    description = "Reverse the text",
    input = {
        text = field.string{required = true, description = "Text to reverse"}
    },
    handler = function(args)
        return string.reverse(args.text)
    end
}

return M
