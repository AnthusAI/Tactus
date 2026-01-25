#!/usr/bin/env python3
"""Test if script mode transformation happens."""

source = """-- Simplest possible test
print("Starting super simple test")

function main()
    print("IN MAIN FUNCTION!")
    return {test = "success"}
end

print("Defined main function")"""

print("Original source:")
print(source)
print("\n" + "="*60 + "\n")

# Check script mode detection
import re

has_explicit_procedure = re.search(r"(?m)^\s*(?:[A-Za-z_][A-Za-z0-9_]*\s*=\s*)?Procedure\b", source)
has_input_output = re.search(r"(?m)^\s*(input|output)\s*\{", source)
has_return = re.search(r"(?m)^\s*return\b", source)

print(f"has_explicit_procedure: {bool(has_explicit_procedure)}")
print(f"has_input_output: {bool(has_input_output)}")
print(f"has_return: {bool(has_return)}")
print(f"\nShould transform: {has_input_output or has_return}")
print(f"Should NOT transform: {has_explicit_procedure or not (has_input_output or has_return)}")
