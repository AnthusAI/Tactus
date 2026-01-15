import pytest

from tactus.formatting import FormattingError, TactusFormatter


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
