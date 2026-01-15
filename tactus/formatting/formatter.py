from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Set

from antlr4 import CommonTokenStream, InputStream
from antlr4.Token import Token
from antlr4.TokenStreamRewriter import TokenStreamRewriter

from tactus.validation.error_listener import TactusErrorListener
from tactus.validation.generated.LuaLexer import LuaLexer
from tactus.validation.generated.LuaParser import LuaParser


class FormattingError(RuntimeError):
    pass


@dataclass(frozen=True)
class FormatResult:
    formatted: str
    changed: bool


class TactusFormatter:
    """
    ANTLR-based formatter for Tactus Lua DSL files.

    Current scope: semantic indentation (2-space soft tabs) while preserving
    token text, comments, and multi-line string/comment contents.
    """

    def __init__(self, indent_width: int = 2):
        if indent_width <= 0:
            raise ValueError("indent_width must be positive")
        self._indent_width = indent_width

    def format_source(self, source: str) -> FormatResult:
        original_source = source
        token_stream, error_listener = self._parse_to_tokens(source)
        if error_listener.errors:
            first = error_listener.errors[0]
            raise FormattingError(f"Cannot format invalid source: {first.message}")

        tokens = list(token_stream.tokens)
        source = _rewrite_token_text(source, tokens, token_stream)
        protected_lines = self._protected_lines_from_multiline_tokens(tokens)
        indent_by_line = self._indentation_by_line(tokens, num_lines=_count_lines(source))

        formatted = _rewrite_leading_indentation(
            source,
            indent_by_line=indent_by_line,
            indent_width=self._indent_width,
            protected_lines=protected_lines,
        )
        return FormatResult(formatted=formatted, changed=(formatted != original_source))

    def format_file(self, file_path: Path) -> FormatResult:
        source = file_path.read_text()
        return self.format_source(source)

    def _parse_to_tokens(self, source: str) -> tuple[CommonTokenStream, TactusErrorListener]:
        input_stream = InputStream(source)
        lexer = LuaLexer(input_stream)
        token_stream = CommonTokenStream(lexer)
        token_stream.fill()

        parser = LuaParser(token_stream)
        error_listener = TactusErrorListener()
        parser.removeErrorListeners()
        parser.addErrorListener(error_listener)
        parser.start_()
        return token_stream, error_listener

    def _protected_lines_from_multiline_tokens(self, tokens: Iterable[Token]) -> Set[int]:
        protected: Set[int] = set()
        for tok in tokens:
            text = getattr(tok, "text", None)
            if not text or "\n" not in text:
                continue

            if tok.type in (LuaLexer.LONGSTRING, LuaLexer.COMMENT):
                start = int(getattr(tok, "line", 0) or 0)
                if start <= 0:
                    continue
                end = start + text.count("\n")
                protected.update(range(start, end + 1))
        return protected

    def _indentation_by_line(self, tokens: Iterable[Token], *, num_lines: int) -> Dict[int, int]:
        line_to_default_tokens: Dict[int, list[Token]] = {}
        for tok in tokens:
            if tok.type == Token.EOF:
                continue
            if tok.channel != Token.DEFAULT_CHANNEL:
                continue
            line_to_default_tokens.setdefault(int(tok.line), []).append(tok)

        open_tokens = {
            LuaLexer.THEN,
            LuaLexer.DO,
            LuaLexer.FUNCTION,
            LuaLexer.REPEAT,
            LuaLexer.OCU,  # {
            LuaLexer.ELSE,
            LuaLexer.ELSEIF,
        }
        close_tokens = {
            LuaLexer.END,
            LuaLexer.UNTIL,
            LuaLexer.CCU,  # }
        }
        dedent_at_line_start = close_tokens | {LuaLexer.ELSE, LuaLexer.ELSEIF}

        indent_level = 0
        indent_by_line: Dict[int, int] = {}

        for line_no in range(1, num_lines + 1):
            tokens_on_line = line_to_default_tokens.get(line_no, [])
            first = tokens_on_line[0] if tokens_on_line else None

            if first is not None and first.type in dedent_at_line_start:
                indent_level = max(0, indent_level - 1)

            indent_by_line[line_no] = indent_level

            handled_first_dedent = first is not None and first.type in dedent_at_line_start
            for idx, tok in enumerate(tokens_on_line):
                if tok.type in close_tokens:
                    if idx == 0 and handled_first_dedent:
                        continue
                    indent_level = max(0, indent_level - 1)
                if tok.type in open_tokens:
                    indent_level += 1

        return indent_by_line


def _count_lines(source: str) -> int:
    if not source:
        return 1
    return source.count("\n") + 1


def _split_line_ending(line: str) -> tuple[str, str]:
    if line.endswith("\r\n"):
        return line[:-2], "\r\n"
    if line.endswith("\n"):
        return line[:-1], "\n"
    if line.endswith("\r"):
        return line[:-1], "\r"
    return line, ""


def _rewrite_leading_indentation(
    source: str,
    *,
    indent_by_line: Dict[int, int],
    indent_width: int,
    protected_lines: Set[int],
) -> str:
    lines = source.splitlines(keepends=True)
    out: list[str] = []

    for i, raw in enumerate(lines, start=1):
        if i in protected_lines:
            out.append(raw)
            continue

        body, ending = _split_line_ending(raw)
        if body.strip() == "":
            out.append(ending)
            continue

        desired = " " * (indent_width * max(0, int(indent_by_line.get(i, 0))))
        stripped = body.lstrip(" \t")
        out.append(desired + stripped + ending)

    return "".join(out)


_LONGSTRING_OPEN_RE = re.compile(r"^\[(?P<eq>=*)\[(?P<body>.*)\](?P=eq)\]$", re.DOTALL)


def _rewrite_token_text(source: str, tokens: list[Token], token_stream: CommonTokenStream) -> str:
    """
    Token-based, semantic rewrites (idempotent):
    - Indent embedded Specifications longstrings.
    - Enforce spaces around '=' (within a single line).
    - Remove trailing commas in multi-line table constructors.
    """
    rewriter = TokenStreamRewriter(token_stream)
    default_tokens: list[Token] = [
        t for t in tokens if t.type != Token.EOF and t.channel == Token.DEFAULT_CHANNEL
    ]

    _apply_specifications_longstring_rewrites(tokens, default_tokens, rewriter)
    _apply_assignment_spacing(default_tokens, tokens, rewriter)
    _apply_comma_spacing(default_tokens, tokens, rewriter)
    _apply_binary_operator_spacing(default_tokens, tokens, rewriter)
    _apply_multiline_table_trailing_comma_removal(default_tokens, tokens, rewriter)

    rewritten = rewriter.getDefaultText()
    return rewritten if rewritten != source else source


def _apply_specifications_longstring_rewrites(
    tokens: list[Token], default_tokens: list[Token], rewriter: TokenStreamRewriter
) -> None:
    longstring_token_indices: list[int] = []
    for idx, tok in enumerate(default_tokens):
        if tok.type != LuaLexer.LONGSTRING:
            continue
        if _is_specifications_call_longstring(default_tokens, idx):
            longstring_token_indices.append(tok.tokenIndex)

    for token_index in longstring_token_indices:
        tok = tokens[token_index]
        new_text = _format_specifications_longstring_text(tok.text or "")
        if new_text != (tok.text or ""):
            rewriter.replaceIndex(token_index, new_text)


def _apply_assignment_spacing(
    default_tokens: list[Token], tokens: list[Token], rewriter: TokenStreamRewriter
) -> None:
    for i, tok in enumerate(default_tokens):
        if tok.type != LuaLexer.EQ:
            continue
        if i == 0 or i + 1 >= len(default_tokens):
            continue

        prev = default_tokens[i - 1]
        nxt = default_tokens[i + 1]
        if prev.line != tok.line or nxt.line != tok.line:
            continue

        # Normalize the hidden token region between prev and '=' to a single space.
        if prev.tokenIndex + 1 <= tok.tokenIndex - 1:
            rewriter.replaceRange(prev.tokenIndex + 1, tok.tokenIndex - 1, " ")
        else:
            rewriter.insertBeforeIndex(tok.tokenIndex, " ")

        # Normalize the hidden token region between '=' and next to a single space.
        if tok.tokenIndex + 1 <= nxt.tokenIndex - 1:
            rewriter.replaceRange(tok.tokenIndex + 1, nxt.tokenIndex - 1, " ")
        else:
            rewriter.insertAfterToken(tok, " ")


def _has_comment_or_newline_between(tokens: list[Token], left: Token, right: Token) -> bool:
    if left.tokenIndex + 1 > right.tokenIndex - 1:
        return False
    for t in tokens[left.tokenIndex + 1 : right.tokenIndex]:
        if t.type in (LuaLexer.NL, LuaLexer.COMMENT):
            return True
    return False


def _apply_comma_spacing(
    default_tokens: list[Token], tokens: list[Token], rewriter: TokenStreamRewriter
) -> None:
    for i, tok in enumerate(default_tokens):
        if tok.type != LuaLexer.COMMA:
            continue
        if i == 0 or i + 1 >= len(default_tokens):
            continue
        prev = default_tokens[i - 1]
        nxt = default_tokens[i + 1]
        if prev.line != tok.line or nxt.line != tok.line:
            continue
        if _has_comment_or_newline_between(tokens, prev, tok) or _has_comment_or_newline_between(
            tokens, tok, nxt
        ):
            continue

        if prev.tokenIndex + 1 <= tok.tokenIndex - 1:
            rewriter.replaceRange(prev.tokenIndex + 1, tok.tokenIndex - 1, "")

        if tok.tokenIndex + 1 <= nxt.tokenIndex - 1:
            rewriter.replaceRange(tok.tokenIndex + 1, nxt.tokenIndex - 1, " ")
        else:
            rewriter.insertAfterToken(tok, " ")


def _apply_binary_operator_spacing(
    default_tokens: list[Token], tokens: list[Token], rewriter: TokenStreamRewriter
) -> None:
    binary_ops = {
        LuaLexer.PLUS,
        LuaLexer.MINUS,
        LuaLexer.STAR,
        LuaLexer.SLASH,
        LuaLexer.PER,
        LuaLexer.SS,  # //
        LuaLexer.DD,  # ..
        LuaLexer.CARET,
        LuaLexer.PIPE,
        LuaLexer.AMP,
        LuaLexer.LL,
        LuaLexer.GG,
        LuaLexer.LT,
        LuaLexer.GT,
        LuaLexer.LE,
        LuaLexer.GE,
        LuaLexer.EE,
        LuaLexer.SQEQ,
        LuaLexer.AND,
        LuaLexer.OR,
    }
    unary_preceders = {
        LuaLexer.EQ,
        LuaLexer.COMMA,
        LuaLexer.OP,
        LuaLexer.OB,
        LuaLexer.OCU,
        LuaLexer.CC,  # '::'
        LuaLexer.THEN,
        LuaLexer.DO,
        LuaLexer.ELSE,
        LuaLexer.ELSEIF,
        LuaLexer.RETURN,
        LuaLexer.FOR,
        LuaLexer.WHILE,
        LuaLexer.IF,
        LuaLexer.IN,
        LuaLexer.AND,
        LuaLexer.OR,
    } | binary_ops

    for i, tok in enumerate(default_tokens):
        if tok.type not in binary_ops:
            continue
        if i == 0 or i + 1 >= len(default_tokens):
            continue
        prev = default_tokens[i - 1]
        nxt = default_tokens[i + 1]
        if prev.line != tok.line or nxt.line != tok.line:
            continue
        if _has_comment_or_newline_between(tokens, prev, tok) or _has_comment_or_newline_between(
            tokens, tok, nxt
        ):
            continue

        if tok.type in (LuaLexer.MINUS, LuaLexer.PLUS) and prev.type in unary_preceders:
            continue

        if prev.tokenIndex + 1 <= tok.tokenIndex - 1:
            rewriter.replaceRange(prev.tokenIndex + 1, tok.tokenIndex - 1, " ")
        else:
            rewriter.insertBeforeIndex(tok.tokenIndex, " ")

        if tok.tokenIndex + 1 <= nxt.tokenIndex - 1:
            rewriter.replaceRange(tok.tokenIndex + 1, nxt.tokenIndex - 1, " ")
        else:
            rewriter.insertAfterToken(tok, " ")


def _apply_multiline_table_trailing_comma_removal(
    default_tokens: list[Token], tokens: list[Token], rewriter: TokenStreamRewriter
) -> None:
    stack: list[int] = []
    for idx, tok in enumerate(default_tokens):
        if tok.type == LuaLexer.OCU:
            stack.append(idx)
            continue
        if tok.type != LuaLexer.CCU:
            continue
        if not stack:
            continue
        open_idx = stack.pop()
        open_tok = default_tokens[open_idx]
        close_tok = tok
        if open_tok.line == close_tok.line:
            continue

        j = idx - 1
        if j <= open_idx:
            continue
        last = default_tokens[j]
        if last.type == LuaLexer.COMMA:
            rewriter.replaceIndex(last.tokenIndex, "")


def _is_specifications_call_longstring(default_tokens: list[Token], longstring_idx: int) -> bool:
    # Accept: Specifications(LONGSTRING) where LONGSTRING is the first argument.
    if longstring_idx < 1:
        return False
    prev = default_tokens[longstring_idx - 1]
    if prev.type == LuaLexer.OP and longstring_idx >= 2:
        name = default_tokens[longstring_idx - 2]
        return name.type == LuaLexer.NAME and (name.text or "") == "Specifications"
    name = prev
    return name.type == LuaLexer.NAME and (name.text or "") == "Specifications"


def _format_specifications_longstring_text(text: str) -> str:
    match = _LONGSTRING_OPEN_RE.match(text)
    if not match:
        return text

    eq = match.group("eq")
    body = match.group("body")
    open_delim = f"[{eq}["
    close_delim = f"]{eq}]"

    formatted_body = _shift_longstring_body_indent_once(body, shift_spaces=2)
    return f"{open_delim}{formatted_body}{close_delim}"


def _shift_longstring_body_indent_once(body: str, *, shift_spaces: int) -> str:
    lines = body.splitlines(keepends=True)
    already_formatted = False
    for line in lines:
        raw, _ending = _split_line_ending(line)
        if raw.strip() == "":
            continue
        expanded = raw.replace("\t", "  ")
        already_formatted = expanded.startswith(" " * shift_spaces)
        break

    if already_formatted:
        return body

    out: list[str] = []
    prefix = " " * shift_spaces
    for line in lines:
        raw, ending = _split_line_ending(line)
        if raw.strip() == "":
            out.append(raw + ending)
            continue

        expanded = raw.replace("\t", "  ")
        out.append(prefix + expanded + ending)
    return "".join(out)
