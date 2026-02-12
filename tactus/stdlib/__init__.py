"""Tactus Standard Library.

The standard library is Tactus-first: modules are implemented in .tac files
under tac/tactus/ and loaded via Lua's require() function.

Python modules exist only as helpers when a Python library is needed
(e.g., rapidfuzz for string similarity, openpyxl for Excel I/O).

## Core Modules (via require)

    local classify = require("tactus.classify")
    local extract = require("tactus.extract")
    local generate = require("tactus.generate")
    local retrievers = require("tactus.retrievers")

## Classify (also available as Lua global)

    result = Classify {
        classes = {"Yes", "No"},
        prompt = "Did the agent greet the customer?",
        input = transcript
    }

## Utility Modules

    local json = require("tactus.io.json")
    local csv = require("tactus.io.csv")
    local file = require("tactus.io.file")

## Python Helpers

Python helper modules in this directory are loaded as fallbacks when
no .tac file exists for a given module name. Examples:
- classify/similarity.py - rapidfuzz-backed string similarity
- io/json.py, io/csv.py, etc. - file format I/O
"""
