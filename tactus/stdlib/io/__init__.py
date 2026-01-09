"""
tactus.stdlib.io - File I/O operations for Tactus procedures.

This package provides Python-backed file I/O modules that can be
imported via require() in .tac files.

Usage:
    local json = require("tactus.io.json")
    local csv = require("tactus.io.csv")
    local file = require("tactus.io.file")

All file operations are sandboxed to the procedure's base directory.
"""
