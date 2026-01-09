#!/usr/bin/env python3
"""
Convert Tactus examples from unnamed Procedure {} to script mode or named procedures.

Strategy:
- Simple examples (no input, simple output): Convert to script mode
- Complex examples: Convert to named procedure (main = Procedure "main" {...})
"""

import re
import sys
from pathlib import Path


def extract_block(text: str, keyword: str) -> tuple[str | None, int, int]:
    """
    Extract a block like 'input = {...}' or 'output = {...}' using proper brace counting.

    Returns: (content_inside_braces, start_pos, end_pos) or (None, -1, -1) if not found
    """
    pattern = rf"{keyword}\s*=\s*{{"
    match = re.search(pattern, text)
    if not match:
        return None, -1, -1

    start = match.end() - 1  # Position of opening brace
    brace_count = 1
    i = start + 1

    while i < len(text) and brace_count > 0:
        if text[i] == "{":
            brace_count += 1
        elif text[i] == "}":
            brace_count -= 1
        i += 1

    if brace_count != 0:
        return None, -1, -1

    # Extract content between braces (excluding the braces themselves)
    content = text[start + 1 : i - 1]
    return content, match.start(), i


def convert_to_script_mode(content: str) -> tuple[str, bool]:
    """
    Convert Procedure {} or Procedure "name" {} to script mode if suitable.

    Returns: (converted_content, was_converted)
    """
    # Check if it has Procedure {} or Procedure "name" {}
    if not re.search(
        r'^(\w+\s*=\s*)?Procedure\s*("[\w-]+")?(\s*"[\w-]+")?\s*\{', content, re.MULTILINE
    ):
        return content, False

    # Extract the Procedure block
    lines = content.split("\n")
    proc_start = None
    for i, line in enumerate(lines):
        # Match: Procedure {, Procedure "name" {, or main = Procedure "main" {
        if re.match(r'^\s*(\w+\s*=\s*)?Procedure\s*("[\w-]+")?(\s*"[\w-]+")?\s*\{', line):
            proc_start = i
            break

    if proc_start is None:
        return content, False

    # Find the matching closing brace
    brace_count = 0
    proc_end = None
    for i in range(proc_start, len(lines)):
        brace_count += lines[i].count("{") - lines[i].count("}")
        if brace_count == 0:
            proc_end = i
            break

    if proc_end is None:
        return content, False

    # Extract before, procedure block, and after
    before = "\n".join(lines[:proc_start])
    proc_block = "\n".join(lines[proc_start : proc_end + 1])
    after = "\n".join(lines[proc_end + 1 :])

    # Parse the Procedure block using proper brace counting
    input_content, _, _ = extract_block(proc_block, "input")
    output_content, _, _ = extract_block(proc_block, "output")

    # Extract function body
    func_match = re.search(r"function\s*\([^)]*\)(.*?)end\s*}\s*$", proc_block, re.DOTALL)
    if not func_match:
        return content, False

    func_body = func_match.group(1).strip()

    # Build script mode version
    parts = [before.rstrip()]
    parts.append("")

    if input_content is not None:
        parts.append(f"input {{{input_content}}}")
        parts.append("")

    if output_content is not None:
        parts.append(f"output {{{output_content}}}")
        parts.append("")

    # Add the function body (unindented)
    body_lines = func_body.split("\n")
    # Remove leading indentation
    min_indent = min(
        (len(line) - len(line.lstrip()) for line in body_lines if line.strip()), default=0
    )
    unindented_body = "\n".join(
        line[min_indent:] if len(line) > min_indent else line for line in body_lines
    )
    parts.append(unindented_body.strip())
    parts.append("")

    if after.strip():
        parts.append(after.strip())

    converted = "\n".join(parts) + "\n"
    return converted, True


def convert_to_named_procedure(content: str) -> tuple[str, bool]:
    """
    Convert unnamed Procedure {} to main = Procedure "main" {...}

    Returns: (converted_content, was_converted)
    """
    # Simple regex replacement
    if not re.search(r"^Procedure\s*\{", content, re.MULTILINE):
        return content, False

    # Replace first occurrence of ^Procedure { with main = Procedure "main" {
    converted = re.sub(
        r"^Procedure\s*\{", 'main = Procedure "main" {', content, count=1, flags=re.MULTILINE
    )

    return converted, converted != content


def main():
    tactus_root = Path("/Users/ryan.porter/Projects/Tactus")
    examples_dir = tactus_root / "examples"

    if not examples_dir.exists():
        print(f"Examples directory not found: {examples_dir}")
        return 1

    # Find all .tac files with Procedure blocks
    files_to_convert = []
    for tac_file in examples_dir.rglob("*.tac"):
        if not tac_file.is_file():
            continue
        content = tac_file.read_text()
        # Match Procedure {, Procedure "name" {, or main = Procedure "main" {
        if re.search(
            r'^(\w+\s*=\s*)?Procedure\s*("[\w-]+")?(\s*"[\w-]+")?\s*\{', content, re.MULTILINE
        ):
            files_to_convert.append(tac_file)

    print(f"Found {len(files_to_convert)} files to convert")

    script_mode_count = 0
    named_proc_count = 0
    failed = []

    for tac_file in files_to_convert:
        try:
            content = tac_file.read_text()

            # Try script mode conversion first
            converted, success = convert_to_script_mode(content)
            if success:
                tac_file.write_text(converted)
                script_mode_count += 1
                print(f"✓ Script mode: {tac_file.relative_to(tactus_root)}")
                continue

            # Fall back to named procedure
            converted, success = convert_to_named_procedure(content)
            if success:
                tac_file.write_text(converted)
                named_proc_count += 1
                print(f"✓ Named proc: {tac_file.relative_to(tactus_root)}")
            else:
                failed.append(tac_file)
                print(f"✗ Failed: {tac_file.relative_to(tactus_root)}")

        except Exception as e:
            failed.append(tac_file)
            print(f"✗ Error in {tac_file.relative_to(tactus_root)}: {e}")

    print("\nSummary:")
    print(f"  Script mode: {script_mode_count}")
    print(f"  Named procedure: {named_proc_count}")
    print(f"  Failed: {len(failed)}")

    if failed:
        print("\nFailed files:")
        for f in failed:
            print(f"  - {f.relative_to(tactus_root)}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
