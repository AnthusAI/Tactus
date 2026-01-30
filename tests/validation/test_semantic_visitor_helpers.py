from types import SimpleNamespace

from tactus.validation.semantic_visitor import TactusDSLVisitor


def test_parse_string_token_variants():
    visitor = TactusDSLVisitor()

    long_token = SimpleNamespace(getText=lambda: "[[Hello\nWorld]]")
    assert visitor._parse_string_token(long_token) == "Hello\nWorld"

    double_token = SimpleNamespace(getText=lambda: '"Hello\\n\\t\\"World\\""')
    assert visitor._parse_string_token(double_token) == 'Hello\n\t"World"'

    single_token = SimpleNamespace(getText=lambda: "'It\\'s ok'")
    assert visitor._parse_string_token(single_token) == "It's ok"


def test_parse_string_handles_missing_context():
    visitor = TactusDSLVisitor()
    assert visitor._parse_string(None) == ""


def test_parse_number_variants():
    visitor = TactusDSLVisitor()

    int_ctx = SimpleNamespace(getText=lambda: "42")
    float_ctx = SimpleNamespace(getText=lambda: "3.14")
    hex_ctx = SimpleNamespace(getText=lambda: "0x10")
    bad_hex_ctx = SimpleNamespace(getText=lambda: "0xZZ")
    bad_ctx = SimpleNamespace(getText=lambda: "nope")

    assert visitor._parse_number(int_ctx) == 42
    assert visitor._parse_number(float_ctx) == 3.14
    assert visitor._parse_number(hex_ctx) == 16
    assert visitor._parse_number(bad_hex_ctx) == 0
    assert visitor._parse_number(bad_ctx) == 0


def test_extract_literal_value_variants():
    visitor = TactusDSLVisitor()

    class FakeStringCtx:
        def __init__(self, text, kind="normal"):
            self._text = text
            self._kind = kind

        def NORMALSTRING(self):
            return SimpleNamespace(getText=lambda: self._text) if self._kind == "normal" else None

        def CHARSTRING(self):
            return SimpleNamespace(getText=lambda: self._text) if self._kind == "char" else None

    class FakeNumberCtx:
        def __init__(self, text, is_int=True):
            self._text = text
            self._is_int = is_int

        def INT(self):
            return SimpleNamespace(getText=lambda: self._text) if self._is_int else None

        def FLOAT(self):
            return SimpleNamespace(getText=lambda: self._text) if not self._is_int else None

    class FakeExp:
        def __init__(self, string_ctx=None, number_ctx=None, text=""):
            self._string = string_ctx
            self._number = number_ctx
            self._text = text

        def string(self):
            return self._string

        def number(self):
            return self._number

        def getText(self):
            return self._text

    assert visitor._extract_literal_value(FakeExp(string_ctx=FakeStringCtx('"hi"'))) == "hi"
    assert visitor._extract_literal_value(FakeExp(string_ctx=FakeStringCtx("'hi'"))) == "hi"
    assert visitor._extract_literal_value(FakeExp(string_ctx=FakeStringCtx("'hi'", kind="char"))) == "hi"
    assert (
        visitor._extract_literal_value(FakeExp(string_ctx=FakeStringCtx('"hi"', kind="char")))
        == "hi"
    )
    assert visitor._extract_literal_value(FakeExp(number_ctx=FakeNumberCtx("7"))) == 7
    assert visitor._extract_literal_value(FakeExp(number_ctx=FakeNumberCtx("3.5", is_int=False))) == 3.5
    assert visitor._extract_literal_value(FakeExp(text="true")) is True
    assert visitor._extract_literal_value(FakeExp(text="false")) is False
    assert visitor._extract_literal_value(FakeExp(text="nil")) is None
    assert visitor._extract_literal_value(FakeExp(text="raw")) == "raw"
    assert visitor._extract_literal_value(None) is None


def test_extract_function_name_fallback_var_or_exp():
    visitor = TactusDSLVisitor()

    class FakeVar:
        def NAME(self):
            return SimpleNamespace(getText=lambda: "Tool")

    class FakeVarOrExp:
        def var(self):
            return FakeVar()

    class FakeCtx:
        def getChildCount(self):
            return 0

        def varOrExp(self):
            return FakeVarOrExp()

    assert visitor._extract_function_name(FakeCtx()) == "Tool"


def test_extract_function_name_from_terminal_child():
    visitor = TactusDSLVisitor()

    class FakeChild:
        symbol = object()

        def getText(self):
            return "Toolset"

    class FakeCtx:
        def getChildCount(self):
            return 1

        def getChild(self, _index):
            return FakeChild()

        def varOrExp(self):
            return None

    assert visitor._extract_function_name(FakeCtx()) == "Toolset"


def test_extract_single_table_arg_returns_empty_for_no_args():
    visitor = TactusDSLVisitor()

    class FakeFuncCall:
        def args(self):
            return []

    assert visitor._extract_single_table_arg(FakeFuncCall()) == {}


def test_extract_single_table_arg_without_table_returns_empty():
    visitor = TactusDSLVisitor()

    class FakeArgs:
        def tableconstructor(self):
            return None

    class FakeFuncCall:
        def args(self):
            return [FakeArgs()]

    assert visitor._extract_single_table_arg(FakeFuncCall()) == {}


def test_extract_arguments_returns_empty_with_no_args():
    visitor = TactusDSLVisitor()

    class FakeCtx:
        def args(self):
            return []

    assert visitor._extract_arguments(FakeCtx()) == []


def test_parse_expression_literal_variants():
    visitor = TactusDSLVisitor()

    class FakeNilCtx:
        def number(self):
            return None

        def string(self):
            return None

        def NIL(self):
            return True

        def FALSE(self):
            return False

        def TRUE(self):
            return False

        def tableconstructor(self):
            return None

        def prefixexp(self):
            return None

    class FakeFalseCtx(FakeNilCtx):
        def NIL(self):
            return False

        def FALSE(self):
            return True

    class FakeTrueCtx(FakeNilCtx):
        def NIL(self):
            return False

        def TRUE(self):
            return True

    assert visitor._parse_expression(None) is None
    assert visitor._parse_expression(FakeNilCtx()) is None
    assert visitor._parse_expression(FakeFalseCtx()) is False
    assert visitor._parse_expression(FakeTrueCtx()) is True


def test_parse_string_context_variants():
    visitor = TactusDSLVisitor()

    class FakeStringCtx:
        def NORMALSTRING(self):
            return None

        def CHARSTRING(self):
            return SimpleNamespace(getText=lambda: "'hi'")

        def LONGSTRING(self):
            return None

    class FakeLongStringCtx:
        def NORMALSTRING(self):
            return None

        def CHARSTRING(self):
            return None

        def LONGSTRING(self):
            return SimpleNamespace(getText=lambda: "[[hi]]")

    class FakeMissingCtx:
        def NORMALSTRING(self):
            return None

        def CHARSTRING(self):
            return None

        def LONGSTRING(self):
            return None

    assert visitor._parse_string(FakeStringCtx()) == "hi"
    assert visitor._parse_string(FakeLongStringCtx()) == "hi"
    assert visitor._parse_string(FakeMissingCtx()) == ""


def test_parse_string_token_fallback_returns_text():
    visitor = TactusDSLVisitor()
    token = SimpleNamespace(getText=lambda: "plain")
    assert visitor._parse_string_token(token) == "plain"


def test_visit_functioncall_reports_processing_error():
    visitor = TactusDSLVisitor()

    class Start:
        line = 1
        column = 2

    class FakeCtx:
        start = Start()

        def getText(self):
            return 'name("demo")'

    def raise_error(*_args, **_kwargs):
        raise ValueError("boom")

    visitor._extract_function_name = lambda _ctx: "name"
    visitor._process_dsl_call = raise_error
    visitor.visitChildren = lambda _ctx: None

    visitor.visitFunctioncall(FakeCtx())

    assert any("Error processing name" in err.message for err in visitor.errors)


def test_visit_functioncall_handles_unexpected_exception():
    visitor = TactusDSLVisitor()

    class FakeCtx:
        start = None

        def getText(self):
            raise RuntimeError("boom")

    visitor.visitChildren = lambda _ctx: None
    visitor.visitFunctioncall(FakeCtx())
