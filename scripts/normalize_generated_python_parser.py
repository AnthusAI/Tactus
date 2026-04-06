#!/usr/bin/env python3
"""
Normalize ANTLR-generated Python parser output for stable static-analysis results.

This script is intentionally deterministic and idempotent.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GENERATED_DIR = ROOT / "tactus" / "validation" / "generated"


def _ensure_explicit_none_return(text: str, function_name: str) -> str:
    marker = f"    def {function_name}("
    start = text.find(marker)
    if start == -1:
        return text

    next_def = text.find("\n    def ", start + 1)
    if next_def == -1:
        block = text[start:]
        suffix = ""
    else:
        block = text[start:next_def]
        suffix = text[next_def:]

    lines = block.splitlines()
    last_code_idx = -1
    for idx, line in enumerate(lines):
        if line.strip():
            last_code_idx = idx
    if last_code_idx == -1:
        return text

    last_line = lines[last_code_idx].strip()
    if last_line == "return None":
        return text

    first_stmt_indent = None
    for line in lines[1:]:
        stripped = line.strip()
        if stripped:
            first_stmt_indent = line[: len(line) - len(line.lstrip())]
            break
    if first_stmt_indent is None:
        first_stmt_indent = "        "

    lines.insert(last_code_idx + 1, f"{first_stmt_indent}return None")
    new_block = "\n".join(lines)
    if block.endswith("\n"):
        new_block += "\n"
    return text[:start] + new_block + suffix


def normalize_parser(text: str) -> str:
    # Unused import in generated parser output.
    text = text.replace("from io import StringIO\n", "")
    # CodeQL warning: test-equals-none
    text = text.replace("if self._predicates == None:", "if self._predicates is None:")
    # CodeQL warning: assignment is not used in generated output.
    text = "".join(
        line for line in text.splitlines(keepends=True) if line.strip() != "_prevctx = localctx"
    )
    # CodeQL warning: mixed explicit/implicit returns.
    text = _ensure_explicit_none_return(text, "exp_sempred")
    text = _ensure_explicit_none_return(text, "prefixexp_sempred")
    return text


def normalize_lexer(text: str) -> str:
    # Unused import in generated lexer output.
    text = text.replace("from io import StringIO\n", "")
    # CodeQL warning: mixed explicit/implicit returns.
    text = _ensure_explicit_none_return(text, "SHEBANG_sempred")
    return text


def _write_if_changed(path: Path, new_text: str) -> bool:
    old_text = path.read_text()
    if old_text == new_text:
        return False
    path.write_text(new_text)
    return True


def main() -> int:
    parser_path = GENERATED_DIR / "LuaParser.py"
    lexer_path = GENERATED_DIR / "LuaLexer.py"

    changed = False
    changed |= _write_if_changed(parser_path, normalize_parser(parser_path.read_text()))
    changed |= _write_if_changed(lexer_path, normalize_lexer(lexer_path.read_text()))

    if changed:
        print("Normalized generated Lua parser/lexer Python files.")
    else:
        print("Generated Lua parser/lexer Python files already normalized.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
