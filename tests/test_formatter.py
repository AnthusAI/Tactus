from types import SimpleNamespace

import pytest

from tactus.formatting import FormattingError, TactusFormatter
from antlr4 import CommonTokenStream
from antlr4.ListTokenSource import ListTokenSource
from antlr4.Token import CommonToken, Token
from antlr4.TokenStreamRewriter import TokenStreamRewriter

from tactus.formatting.formatter import (
    _apply_assignment_spacing,
    _apply_binary_operator_spacing,
    _apply_comma_spacing,
    _apply_multiline_table_trailing_comma_removal,
    _apply_specifications_longstring_rewrites,
    _count_lines,
    _format_specifications_longstring_text,
    _has_comment_or_newline_between,
    _is_specifications_call_longstring,
    _rewrite_leading_indentation,
    _shift_longstring_body_indent_once,
    _split_line_ending,
)
from tactus.validation.generated.LuaLexer import LuaLexer


def test_formatter_is_idempotent():
    src = """-- formatting test

Procedure {
\toutput = {
\tgreeting=field.string{required=true},
\tcompleted=field.boolean{required=true},
\t},
\tfunction(input)
\tif 1<2 and 3>4 then
\treturn {greeting="hi",completed=true}
\tend
\tend
}
"""
    formatter = TactusFormatter(indent_width=2)
    first = formatter.format_source(src).formatted
    assert (
        first
        == """-- formatting test

Procedure {
  output = {
    greeting = field.string{required = true},
    completed = field.boolean{required = true}
  },
  function(input)
    if 1 < 2 and 3 > 4 then
      return {greeting = "hi", completed = true}
    end
  end
}
"""
    )
    second = formatter.format_source(first).formatted
    assert first == second


def test_formatter_removes_tab_indentation():
    src = "Procedure {\n\tfunction(input)\n\treturn 1\n\tend\n}\n"
    formatter = TactusFormatter(indent_width=2)
    formatted = formatter.format_source(src).formatted
    for line in formatted.splitlines():
        prefix = line[: len(line) - len(line.lstrip(" \t"))]
        assert "\t" not in prefix
        if line.strip():
            assert len(prefix) % 2 == 0


def test_formatter_rejects_invalid_source():
    src = "Procedure {\n  function(input)\n    if true then\n  end\n"
    formatter = TactusFormatter(indent_width=2)
    with pytest.raises(FormattingError):
        formatter.format_source(src)


def test_formatter_indents_specifications_longstring():
    src = """Specifications([[
Feature: Simple State Management
  Test basic state and stage functionality without agents
]])\n"""
    formatter = TactusFormatter(indent_width=2)
    formatted = formatter.format_source(src).formatted
    assert (
        formatted
        == """Specifications([[
  Feature: Simple State Management
    Test basic state and stage functionality without agents
]])\n"""
    )

    assert formatter.format_source(formatted).formatted == formatted


def test_formatter_rejects_non_positive_indent_width():
    with pytest.raises(ValueError):
        TactusFormatter(indent_width=0)


def test_formatter_formats_file(tmp_path):
    source = "Procedure {\n  function(input)\n    return 1\n  end\n}\n"
    path = tmp_path / "example.tac"
    path.write_text(source)

    formatter = TactusFormatter(indent_width=2)
    result = formatter.format_file(path)

    assert result.formatted == source
    assert result.changed is False


def test_count_lines_and_split_endings():
    assert _count_lines("") == 1
    assert _count_lines("a\nb") == 2

    assert _split_line_ending("a\r\n") == ("a", "\r\n")
    assert _split_line_ending("a\n") == ("a", "\n")
    assert _split_line_ending("a\r") == ("a", "\r")
    assert _split_line_ending("a") == ("a", "")


def test_protected_lines_skips_nonpositive_line_numbers():
    formatter = TactusFormatter(indent_width=2)
    tokens = [
        SimpleNamespace(type=LuaLexer.LONGSTRING, text="a\nb", line=0),
        SimpleNamespace(type=LuaLexer.LONGSTRING, text="a\nb", line=2),
    ]
    protected = formatter._protected_lines_from_multiline_tokens(tokens)
    assert protected == {2, 3}


def test_rewrite_leading_indentation_respects_blank_and_protected_lines():
    source = "  keep\n\n  trim\n"
    indent_by_line = {1: 0, 2: 0, 3: 2}
    protected_lines = {1}

    result = _rewrite_leading_indentation(
        source,
        indent_by_line=indent_by_line,
        indent_width=2,
        protected_lines=protected_lines,
    )

    assert result == "  keep\n\n    trim\n"


def test_format_specifications_longstring_text_no_match():
    assert _format_specifications_longstring_text("not a longstring") == "not a longstring"


def test_shift_longstring_body_indent_once_when_already_formatted():
    body = "\n  Feature: Demo\n"
    assert _shift_longstring_body_indent_once(body, shift_spaces=2) == body


def test_shift_longstring_body_indent_once_when_leading_spaces_present():
    body = "  Feature: Demo\n"
    assert _shift_longstring_body_indent_once(body, shift_spaces=2) == body


def test_shift_longstring_body_indent_once_when_only_blank_lines():
    body = "\n\n"
    assert _shift_longstring_body_indent_once(body, shift_spaces=2) == body


def _make_token(token_type, text="", line=1, channel=Token.DEFAULT_CHANNEL):
    token = CommonToken(type=token_type)
    token.text = text
    token.line = line
    token.channel = channel
    return token


def _build_stream(tokens):
    for idx, token in enumerate(tokens):
        token.tokenIndex = idx
    stream = CommonTokenStream(ListTokenSource(tokens))
    stream.fill()
    return stream


def test_assignment_spacing_skips_edge_tokens():
    tokens = [_make_token(LuaLexer.EQ, "=", line=1)]
    stream = _build_stream(tokens)
    rewriter = TokenStreamRewriter(stream)
    _apply_assignment_spacing(tokens, tokens, rewriter)


def test_assignment_spacing_skips_cross_line_assignments():
    tokens = [
        _make_token(LuaLexer.NAME, "a", line=1),
        _make_token(LuaLexer.EQ, "=", line=1),
        _make_token(LuaLexer.NAME, "b", line=2),
    ]
    stream = _build_stream(tokens)
    rewriter = TokenStreamRewriter(stream)
    _apply_assignment_spacing(tokens, tokens, rewriter)


def test_comma_spacing_skips_edge_tokens():
    tokens = [_make_token(LuaLexer.COMMA, ",", line=1)]
    stream = _build_stream(tokens)
    rewriter = TokenStreamRewriter(stream)
    _apply_comma_spacing(tokens, tokens, rewriter)


def test_comma_spacing_skips_comment_between():
    tokens = [
        _make_token(LuaLexer.NAME, "a", line=1),
        _make_token(LuaLexer.COMMENT, "--x", line=1, channel=Token.HIDDEN_CHANNEL),
        _make_token(LuaLexer.COMMA, ",", line=1),
        _make_token(LuaLexer.NAME, "b", line=1),
    ]
    stream = _build_stream(tokens)
    rewriter = TokenStreamRewriter(stream)
    default_tokens = [token for token in tokens if token.channel == Token.DEFAULT_CHANNEL]
    _apply_comma_spacing(default_tokens, tokens, rewriter)


def test_comma_spacing_trims_hidden_space():
    tokens = [
        _make_token(LuaLexer.NAME, "a", line=1),
        _make_token(LuaLexer.WS, " ", line=1, channel=Token.HIDDEN_CHANNEL),
        _make_token(LuaLexer.COMMA, ",", line=1),
        _make_token(LuaLexer.WS, " ", line=1, channel=Token.HIDDEN_CHANNEL),
        _make_token(LuaLexer.NAME, "b", line=1),
    ]
    stream = _build_stream(tokens)
    rewriter = TokenStreamRewriter(stream)
    default_tokens = [token for token in tokens if token.channel == Token.DEFAULT_CHANNEL]
    _apply_comma_spacing(default_tokens, tokens, rewriter)


def test_binary_operator_spacing_skips_edge_tokens():
    tokens = [_make_token(LuaLexer.PLUS, "+", line=1)]
    stream = _build_stream(tokens)
    rewriter = TokenStreamRewriter(stream)
    _apply_binary_operator_spacing(tokens, tokens, rewriter)


def test_binary_operator_spacing_skips_cross_line():
    tokens = [
        _make_token(LuaLexer.NAME, "a", line=1),
        _make_token(LuaLexer.PLUS, "+", line=1),
        _make_token(LuaLexer.NAME, "b", line=2),
    ]
    stream = _build_stream(tokens)
    rewriter = TokenStreamRewriter(stream)
    _apply_binary_operator_spacing(tokens, tokens, rewriter)


def test_binary_operator_spacing_skips_comment_between():
    tokens = [
        _make_token(LuaLexer.NAME, "a", line=1),
        _make_token(LuaLexer.COMMENT, "--x", line=1, channel=Token.HIDDEN_CHANNEL),
        _make_token(LuaLexer.PLUS, "+", line=1),
        _make_token(LuaLexer.NAME, "b", line=1),
    ]
    stream = _build_stream(tokens)
    rewriter = TokenStreamRewriter(stream)
    default_tokens = [token for token in tokens if token.channel == Token.DEFAULT_CHANNEL]
    _apply_binary_operator_spacing(default_tokens, tokens, rewriter)


def test_has_comment_or_newline_between_detects_comment():
    tokens = [
        _make_token(LuaLexer.NAME, "a", line=1),
        _make_token(LuaLexer.COMMENT, "--x", line=1),
        _make_token(LuaLexer.NAME, "b", line=1),
    ]
    _build_stream(tokens)
    assert _has_comment_or_newline_between(tokens, tokens[0], tokens[2]) is True


def test_binary_operator_spacing_skips_unary_minus():
    tokens = [
        _make_token(LuaLexer.RETURN, "return", line=1),
        _make_token(LuaLexer.MINUS, "-", line=1),
        _make_token(LuaLexer.INT, "1", line=1),
    ]
    stream = _build_stream(tokens)
    rewriter = TokenStreamRewriter(stream)
    _apply_binary_operator_spacing(tokens, tokens, rewriter)


def test_multiline_table_trailing_comma_removal_skips_unmatched_close():
    tokens = [_make_token(LuaLexer.CCU, "}", line=2)]
    stream = _build_stream(tokens)
    rewriter = TokenStreamRewriter(stream)
    _apply_multiline_table_trailing_comma_removal(tokens, tokens, rewriter)


def test_multiline_table_trailing_comma_removal_skips_empty_table():
    tokens = [
        _make_token(LuaLexer.OCU, "{", line=1),
        _make_token(LuaLexer.CCU, "}", line=2),
    ]
    stream = _build_stream(tokens)
    rewriter = TokenStreamRewriter(stream)
    _apply_multiline_table_trailing_comma_removal(tokens, tokens, rewriter)


def test_is_specifications_call_longstring_variants():
    tokens = [_make_token(LuaLexer.LONGSTRING, "[[x]]", line=1)]
    assert _is_specifications_call_longstring(tokens, 0) is False

    tokens = [
        _make_token(LuaLexer.NAME, "Other", line=1),
        _make_token(LuaLexer.LONGSTRING, "[[x]]", line=1),
    ]
    assert _is_specifications_call_longstring(tokens, 1) is False

    tokens = [
        _make_token(LuaLexer.NAME, "Specifications", line=1),
        _make_token(LuaLexer.OP, "(", line=1),
        _make_token(LuaLexer.LONGSTRING, "[[x]]", line=1),
    ]
    assert _is_specifications_call_longstring(tokens, 2) is True


def test_apply_specifications_longstring_skips_non_spec_call():
    tokens = [
        _make_token(LuaLexer.NAME, "Other", line=1),
        _make_token(LuaLexer.OP, "(", line=1),
        _make_token(LuaLexer.LONGSTRING, "[[x]]", line=1),
    ]
    stream = _build_stream(tokens)
    rewriter = TokenStreamRewriter(stream)
    default_tokens = [token for token in tokens if token.channel == Token.DEFAULT_CHANNEL]
    _apply_specifications_longstring_rewrites(tokens, default_tokens, rewriter)
