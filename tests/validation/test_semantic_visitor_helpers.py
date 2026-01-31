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
    assert (
        visitor._extract_literal_value(FakeExp(string_ctx=FakeStringCtx("'hi'", kind="char")))
        == "hi"
    )
    assert (
        visitor._extract_literal_value(FakeExp(string_ctx=FakeStringCtx('"hi"', kind="char")))
        == "hi"
    )
    assert visitor._extract_literal_value(FakeExp(number_ctx=FakeNumberCtx("7"))) == 7
    assert (
        visitor._extract_literal_value(FakeExp(number_ctx=FakeNumberCtx("3.5", is_int=False)))
        == 3.5
    )
    assert visitor._extract_literal_value(FakeExp(text="true")) is True
    assert visitor._extract_literal_value(FakeExp(text="false")) is False
    assert visitor._extract_literal_value(FakeExp(text="nil")) is None
    assert visitor._extract_literal_value(FakeExp(text="raw")) == "raw"
    assert visitor._extract_literal_value(None) is None


def test_extract_literal_value_with_single_quote_normal_string():
    visitor = TactusDSLVisitor()

    class FakeStringCtx:
        def NORMALSTRING(self):
            return SimpleNamespace(getText=lambda: "'hello'")

        def CHARSTRING(self):
            return None

    class FakeExp:
        def string(self):
            return FakeStringCtx()

        def number(self):
            return None

        def getText(self):
            return "'hello'"

    assert visitor._extract_literal_value(FakeExp()) == "hello"


def test_extract_literal_value_charstring_double_quote():
    visitor = TactusDSLVisitor()

    class FakeStringCtx:
        def NORMALSTRING(self):
            return None

        def CHARSTRING(self):
            return SimpleNamespace(getText=lambda: '"hi"')

    class FakeExp:
        def string(self):
            return FakeStringCtx()

        def number(self):
            return None

        def getText(self):
            return '"hi"'

    assert visitor._extract_literal_value(FakeExp()) == "hi"


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


def test_extract_function_name_skips_non_identifier_child():
    visitor = TactusDSLVisitor()

    class FakeChild:
        symbol = object()

        def getText(self):
            return "123"

    class FakeVar:
        def NAME(self):
            return SimpleNamespace(getText=lambda: "Agent")

    class FakeVarOrExp:
        def var(self):
            return FakeVar()

    class FakeCtx:
        def getChildCount(self):
            return 1

        def getChild(self, _index):
            return FakeChild()

        def varOrExp(self):
            return FakeVarOrExp()

    assert visitor._extract_function_name(FakeCtx()) == "Agent"


def test_extract_function_name_returns_none_without_name():
    visitor = TactusDSLVisitor()

    class FakeVar:
        def NAME(self):
            return None

    class FakeVarOrExp:
        def var(self):
            return FakeVar()

    class FakeCtx:
        def getChildCount(self):
            return 0

        def varOrExp(self):
            return FakeVarOrExp()

    assert visitor._extract_function_name(FakeCtx()) is None


def test_extract_function_name_returns_none_when_no_var_or_exp():
    visitor = TactusDSLVisitor()

    class FakeCtx:
        def getChildCount(self):
            return 0

        def varOrExp(self):
            return None

    assert visitor._extract_function_name(FakeCtx()) is None


def test_extract_function_name_var_or_exp_without_var():
    visitor = TactusDSLVisitor()

    class FakeVarOrExp:
        def var(self):
            return None

    class FakeCtx:
        def getChildCount(self):
            return 0

        def varOrExp(self):
            return FakeVarOrExp()

    assert visitor._extract_function_name(FakeCtx()) is None


def test_extract_single_table_arg_handles_missing_table():
    visitor = TactusDSLVisitor()

    class FakeArgs:
        def tableconstructor(self):
            return None

    class FakeCall:
        def args(self):
            return [FakeArgs()]

    assert visitor._extract_single_table_arg(FakeCall()) == {}


def test_extract_single_table_arg_parses_table():
    visitor = TactusDSLVisitor()

    class FakeTable:
        pass

    class FakeArgs:
        def tableconstructor(self):
            return FakeTable()

    class FakeCall:
        def args(self):
            return [FakeArgs()]

    visitor._parse_table_constructor = lambda _ctx: {"ok": True}
    assert visitor._extract_single_table_arg(FakeCall()) == {"ok": True}


def test_visit_functioncall_skips_method_call():
    visitor = TactusDSLVisitor()

    class FakeChild:
        symbol = object()

        def getText(self):
            return "Tool"

    class FakeCtx:
        start = None

        def getChildCount(self):
            return 1

        def getChild(self, _index):
            return FakeChild()

        def varOrExp(self):
            return None

        def getText(self):
            return "Tool.called({})"

    visitor._check_deprecated_method_calls = lambda _ctx: None
    visitor._process_dsl_call = lambda *_args, **_kwargs: (_ for _ in ()).throw(
        AssertionError("should not process method call")
    )
    visitor.visitChildren = lambda _ctx: None

    visitor.visitFunctioncall(FakeCtx())


def test_extract_arguments_detects_method_chain():
    visitor = TactusDSLVisitor()
    visitor._parse_string = lambda _ctx: "name"

    class FakeArgs:
        def __init__(self, is_string):
            self._is_string = is_string

        def explist(self):
            return None

        def tableconstructor(self):
            return None

        def string(self):
            return object() if self._is_string else None

    class FakeCtx:
        def __init__(self):
            self._args = [FakeArgs(True), FakeArgs(False)]
            self._children = [
                self._args[0],
                SimpleNamespace(symbol=True, getText=lambda: "."),
                self._args[1],
            ]

        def args(self):
            return self._args

        def getChildCount(self):
            return len(self._children)

        def getChild(self, index):
            return self._children[index]

    args = visitor._extract_arguments(FakeCtx())
    assert args == ["name"]


def test_parse_expression_field_builder_with_options():
    visitor = TactusDSLVisitor()

    class FakeFieldArgs:
        def tableconstructor(self):
            return object()

    class FakeFuncCall:
        def NAME(self):
            return [
                SimpleNamespace(getText=lambda: "field"),
                SimpleNamespace(getText=lambda: "string"),
            ]

        def args(self, index=None):  # noqa: A003 - match parser style
            if index is None:
                return [FakeFieldArgs()]
            return FakeFieldArgs()

    class FakePrefix:
        def functioncall(self):
            return FakeFuncCall()

    class FakeExp:
        def prefixexp(self):
            return FakePrefix()

        def number(self):
            return None

        def string(self):
            return None

        def NIL(self):
            return None

        def FALSE(self):
            return None

        def TRUE(self):
            return None

        def tableconstructor(self):
            return None

    visitor._parse_table_constructor = lambda _ctx: {
        "required": False,
        "default": "ok",
        "description": "demo",
        "enum": ["a"],
    }

    field_def = visitor._parse_expression(FakeExp())
    assert field_def["required"] is False
    assert field_def["default"] == "ok"
    assert field_def["description"] == "demo"
    assert field_def["enum"] == ["a"]


def test_parse_table_constructor_array_element():
    visitor = TactusDSLVisitor()

    class FakeExp:
        def number(self):
            return None

        def string(self):
            return None

        def NIL(self):
            return None

        def FALSE(self):
            return None

        def TRUE(self):
            return None

        def tableconstructor(self):
            return None

        def prefixexp(self):
            return None

    class FakeField:
        def NAME(self):
            return None

        def exp(self, index=None):  # noqa: A003 - match parser style
            if index is None:
                return [FakeExp()]
            return FakeExp()

    class FakeFieldList:
        def field(self):
            return [FakeField()]

    class FakeTable:
        def fieldlist(self):
            return FakeFieldList()

    visitor._parse_expression = lambda _ctx: "item"
    assert visitor._parse_table_constructor(FakeTable()) == ["item"]


def test_process_dsl_call_model_name_only():
    visitor = TactusDSLVisitor()
    visitor._extract_arguments = lambda _ctx: ["demo_model"]

    visitor._process_dsl_call("Model", SimpleNamespace())
    assert "demo_model" in visitor.builder.registry.models


def test_process_dsl_call_toolset_registers():
    visitor = TactusDSLVisitor()
    visitor._extract_arguments = lambda _ctx: ["tools", {"tools": ["a"]}]

    visitor._process_dsl_call("Toolset", SimpleNamespace())
    assert "tools" in visitor.builder.registry.toolsets


def test_visit_stat_skips_missing_varlist():
    class Visitor(TactusDSLVisitor):
        def visitChildren(self, ctx):
            return "visited"

    visitor = Visitor()

    class FakeCtx:
        def varlist(self):
            return None

        def explist(self):
            return None

    assert visitor.visitStat(FakeCtx()) == "visited"


def test_visit_stat_sets_default_values():
    calls = {}

    class Builder:
        def __getattr__(self, name):
            if name.startswith("set_"):
                return lambda *_args, **_kwargs: None
            raise AttributeError(name)

        def set_max_turns(self, value):
            calls["max_turns"] = value

        def __getattr__(self, name):  # noqa: F811
            if name.startswith("set_"):
                return lambda _value: None
            raise AttributeError(name)

    class Visitor(TactusDSLVisitor):
        def visitChildren(self, ctx):
            return "visited"

    visitor = Visitor()
    visitor.builder = Builder()
    visitor._extract_literal_value = lambda _exp: 5

    class FakeVar:
        def NAME(self):
            return SimpleNamespace(getText=lambda: "max_turns")

    class FakeVarlist:
        def var(self):
            return [FakeVar()]

    class FakeExplist:
        def exp(self):
            return [SimpleNamespace()]

    class FakeCtx:
        def varlist(self):
            return FakeVarlist()

        def explist(self):
            return FakeExplist()

    assert visitor.visitStat(FakeCtx()) == "visited"
    assert calls["max_turns"] == 5


def test_visit_stat_sets_other_defaults():
    calls = {}

    class Builder:
        def set_default_provider(self, value):
            calls["default_provider"] = value

        def set_return_prompt(self, value):
            calls["return_prompt"] = value

        def __getattr__(self, name):  # noqa: F811
            if name.startswith("set_"):
                return lambda _value: None
            raise AttributeError(name)

    class Visitor(TactusDSLVisitor):
        def visitChildren(self, ctx):
            return "visited"

    visitor = Visitor()
    visitor.builder = Builder()

    class FakeVar:
        def __init__(self, name):
            self._name = name

        def NAME(self):
            return SimpleNamespace(getText=lambda: self._name)

    class FakeVarlist:
        def __init__(self, name):
            self._name = name

        def var(self):
            return [FakeVar(self._name)]

    class FakeExplist:
        def exp(self):
            return [SimpleNamespace()]

    class FakeCtx:
        def __init__(self, name):
            self._name = name

        def varlist(self):
            return FakeVarlist(self._name)

        def explist(self):
            return FakeExplist()

    visitor._extract_literal_value = lambda _exp: "value"
    assert visitor.visitStat(FakeCtx("default_provider")) == "visited"
    assert calls["default_provider"] == "value"

    visitor._extract_literal_value = lambda _exp: "prompt"
    assert visitor.visitStat(FakeCtx("return_prompt")) == "visited"
    assert calls["return_prompt"] == "prompt"


def test_visit_stat_assignment_fallback():
    calls = {}

    class Builder:
        def __getattr__(self, name):
            if name.startswith("set_"):
                return lambda *_args, **_kwargs: None
            raise AttributeError(name)

        def set_max_turns(self, value):
            calls["max_turns"] = value

        def __getattr__(self, name):  # noqa: F811
            if name.startswith("set_"):
                return lambda _value: None
            raise AttributeError(name)

    class Visitor(TactusDSLVisitor):
        def visitChildren(self, ctx):
            return "visited"

    visitor = Visitor()
    visitor.builder = Builder()

    def fake_check(name, exp):
        calls["checked"] = (name, exp)

    visitor._check_assignment_based_declaration = fake_check

    class FakeVar:
        def NAME(self):
            return SimpleNamespace(getText=lambda: "custom")

    class FakeVarlist:
        def var(self):
            return [FakeVar()]

    class FakeExplist:
        def exp(self):
            return [SimpleNamespace()]

    class FakeCtx:
        def varlist(self):
            return FakeVarlist()

        def explist(self):
            return FakeExplist()

    assert visitor.visitStat(FakeCtx()) == "visited"
    assert calls["checked"][0] == "custom"


def test_assignment_based_declaration_filters_tools_none():
    calls = {}

    class Builder:
        def register_agent(self, name, config, _ctx):
            calls["agent"] = (name, config)

    visitor = TactusDSLVisitor()
    visitor.builder = Builder()
    visitor._extract_function_name = lambda _ctx: "Agent"
    visitor._extract_single_table_arg = lambda _ctx: {"tools": ["tool", None]}

    class FakeFuncCall:
        def getChildCount(self):
            return 1

    class FakePrefixExp:
        def functioncall(self):
            return FakeFuncCall()

    class FakeExp:
        def prefixexp(self):
            return FakePrefixExp()

    visitor._check_assignment_based_declaration("greeter", FakeExp())
    assert calls["agent"][0] == "greeter"
    assert calls["agent"][1]["tools"] == ["tool"]


def test_visit_stat_with_empty_varlist_and_explist():
    class Visitor(TactusDSLVisitor):
        def visitChildren(self, ctx):
            return "visited"

    visitor = Visitor()

    class FakeVarlist:
        def var(self):
            return []

    class FakeExplist:
        def exp(self):
            return []

    class FakeCtx:
        def varlist(self):
            return FakeVarlist()

        def explist(self):
            return FakeExplist()

    assert visitor.visitStat(FakeCtx()) == "visited"


def test_visit_stat_with_missing_explist_values():
    class Visitor(TactusDSLVisitor):
        def visitChildren(self, ctx):
            return "visited"

    visitor = Visitor()

    class FakeVar:
        def NAME(self):
            return SimpleNamespace(getText=lambda: "max_turns")

    class FakeVarlist:
        def var(self):
            return [FakeVar()]

    class FakeExplist:
        def exp(self):
            return []

    class FakeCtx:
        def varlist(self):
            return FakeVarlist()

        def explist(self):
            return FakeExplist()

    assert visitor.visitStat(FakeCtx()) == "visited"


def test_visit_stat_checks_assignment_when_explist_present():
    called = {}

    class Visitor(TactusDSLVisitor):
        def visitChildren(self, ctx):
            return "visited"

    visitor = Visitor()
    visitor._check_assignment_based_declaration = lambda name, exp: called.setdefault(
        "value", (name, exp)
    )

    class FakeVar:
        def NAME(self):
            return SimpleNamespace(getText=lambda: "custom")

    class FakeVarlist:
        def var(self):
            return [FakeVar()]

    class FakeExplist:
        def exp(self):
            return [SimpleNamespace()]

    class FakeCtx:
        def varlist(self):
            return FakeVarlist()

        def explist(self):
            return FakeExplist()

    assert visitor.visitStat(FakeCtx()) == "visited"
    assert called["value"][0] == "custom"


def test_visit_stat_assignment_without_explist_values():
    called = {}

    class Visitor(TactusDSLVisitor):
        def visitChildren(self, ctx):
            return "visited"

    visitor = Visitor()

    def fake_check(name, exp):
        called["name"] = name

    visitor._check_assignment_based_declaration = fake_check

    class FakeVar:
        def NAME(self):
            return SimpleNamespace(getText=lambda: "custom")

    class FakeVarlist:
        def var(self):
            return [FakeVar()]

    class FakeExplist:
        def exp(self):
            return []

    class FakeCtx:
        def varlist(self):
            return FakeVarlist()

        def explist(self):
            return FakeExplist()

    assert visitor.visitStat(FakeCtx()) == "visited"
    assert "name" not in called


def test_process_dsl_call_with_empty_args():
    class Builder:
        def set_name(self, _value):
            raise AssertionError("should not be called")

        def set_version(self, _value):
            raise AssertionError("should not be called")

        def register_model(self, *_args, **_kwargs):
            raise AssertionError("should not be called")

        def register_named_procedure(self, *_args, **_kwargs):
            raise AssertionError("should not be called")

        def register_input_schema(self, *_args, **_kwargs):
            raise AssertionError("should not be called")

        def register_output_schema(self, *_args, **_kwargs):
            raise AssertionError("should not be called")

        def register_state_schema(self, *_args, **_kwargs):
            raise AssertionError("should not be called")

        def register_evaluations(self, *_args, **_kwargs):
            raise AssertionError("should not be called")

        def set_evaluation_config(self, *_args, **_kwargs):
            raise AssertionError("should not be called")

        def register_specifications(self, *_args, **_kwargs):
            raise AssertionError("should not be called")

        def register_prompt(self, *_args, **_kwargs):
            raise AssertionError("should not be called")

        def register_hitl(self, *_args, **_kwargs):
            raise AssertionError("should not be called")

        def register_specification(self, *_args, **_kwargs):
            raise AssertionError("should not be called")

        def register_custom_step(self, *_args, **_kwargs):
            raise AssertionError("should not be called")

        def register_evaluations(self, *_args, **_kwargs):  # noqa: F811
            raise AssertionError("should not be called")

        def set_default_provider(self, *_args, **_kwargs):
            raise AssertionError("should not be called")

        def set_default_model(self, *_args, **_kwargs):
            raise AssertionError("should not be called")

        def set_return_prompt(self, *_args, **_kwargs):
            raise AssertionError("should not be called")

        def set_error_prompt(self, *_args, **_kwargs):
            raise AssertionError("should not be called")

        def set_status_prompt(self, *_args, **_kwargs):
            raise AssertionError("should not be called")

    visitor = TactusDSLVisitor()
    visitor.builder = Builder()
    visitor._extract_arguments = lambda _ctx: []

    class FakeCtx:
        def getChildCount(self):
            return 0

        def varOrExp(self):
            return None

    ctx = FakeCtx()
    visitor._process_dsl_call("name", ctx)
    visitor._process_dsl_call("version", ctx)
    visitor._process_dsl_call("Model", ctx)
    visitor._process_dsl_call("Procedure", ctx)
    visitor._process_dsl_call("Evaluation", ctx)
    visitor._process_dsl_call("Specifications", ctx)
    visitor._process_dsl_call("Prompt", ctx)
    visitor._process_dsl_call("Hitl", ctx)
    visitor._process_dsl_call("Specification", ctx)
    visitor._process_dsl_call("Step", ctx)
    visitor._process_dsl_call("Evaluations", ctx)
    visitor._process_dsl_call("default_provider", ctx)
    visitor._process_dsl_call("default_model", ctx)
    visitor._process_dsl_call("return_prompt", ctx)
    visitor._process_dsl_call("error_prompt", ctx)
    visitor._process_dsl_call("status_prompt", ctx)


def test_visit_functioncall_method_access_skips():
    class Visitor(TactusDSLVisitor):
        def visitChildren(self, ctx):
            return "visited"

    visitor = Visitor()

    class FakeStart:
        line = 1
        column = 2

    class FakeCtx:
        start = FakeStart()

        def getText(self):
            return "Tool.called()"

        def getChildCount(self):
            return 1

        def getChild(self, _index):
            return SimpleNamespace(symbol=object(), getText=lambda: "Tool")

        def varOrExp(self):
            return None

    assert visitor.visitFunctioncall(FakeCtx()) == "visited"


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


def test_extract_arguments_handles_method_chain():
    visitor = TactusDSLVisitor()

    class FakeExpList:
        def __init__(self, values):
            self._values = values

        def exp(self):
            return self._values

    class FakeArgs:
        def __init__(self, values=None):
            self._values = values or []

        def explist(self):
            return FakeExpList(self._values)

        def tableconstructor(self):
            return None

        def string(self):
            return None

    first_exp = SimpleNamespace(name="first")
    second_exp = SimpleNamespace(name="second")
    args_list = [FakeArgs([first_exp]), FakeArgs([second_exp])]

    class FakeToken:
        symbol = object()

        def __init__(self, text):
            self._text = text

        def getText(self):
            return self._text

    class FakeCtx:
        def args(self):
            return args_list

        def getChildCount(self):
            return 3

        def getChild(self, index):
            return [args_list[0], FakeToken("."), args_list[1]][index]

    visitor._parse_expression = lambda exp: exp.name

    assert visitor._extract_arguments(FakeCtx()) == ["first"]


def test_extract_arguments_handles_method_chain_with_colon():
    visitor = TactusDSLVisitor()

    class FakeExpList:
        def __init__(self, values):
            self._values = values

        def exp(self):
            return self._values

    class FakeArgs:
        def __init__(self, values=None):
            self._values = values or []

        def explist(self):
            return FakeExpList(self._values)

        def tableconstructor(self):
            return None

        def string(self):
            return None

    first_exp = SimpleNamespace(name="first")
    second_exp = SimpleNamespace(name="second")
    args_list = [FakeArgs([first_exp]), FakeArgs([second_exp])]

    class FakeToken:
        symbol = object()

        def __init__(self, text):
            self._text = text

        def getText(self):
            return self._text

    class FakeCtx:
        def args(self):
            return args_list

        def getChildCount(self):
            return 3

        def getChild(self, index):
            return [args_list[0], FakeToken(":"), args_list[1]][index]

    visitor._parse_expression = lambda exp: exp.name

    assert visitor._extract_arguments(FakeCtx()) == ["first"]


def test_extract_arguments_handles_symbol_between_args():
    visitor = TactusDSLVisitor()

    class FakeExpList:
        def __init__(self, values):
            self._values = values

        def exp(self):
            return self._values

    class FakeArgs:
        def __init__(self, values=None):
            self._values = values or []

        def explist(self):
            return FakeExpList(self._values)

        def tableconstructor(self):
            return None

        def string(self):
            return None

    first_exp = SimpleNamespace(name="first")
    second_exp = SimpleNamespace(name="second")
    args_list = [FakeArgs([first_exp]), FakeArgs([second_exp])]

    class FakeToken:
        symbol = object()

        def __init__(self, text):
            self._text = text

        def getText(self):
            return self._text

    class FakeCtx:
        def args(self):
            return args_list

        def getChildCount(self):
            return 3

        def getChild(self, index):
            return [args_list[0], FakeToken("+"), args_list[1]][index]

    visitor._parse_expression = lambda exp: exp.name

    assert visitor._extract_arguments(FakeCtx()) == ["first", "second"]


def test_extract_arguments_handles_shorthand():
    visitor = TactusDSLVisitor()

    class FakeExpList:
        def __init__(self, values):
            self._values = values

        def exp(self):
            return self._values

    class FakeArgs:
        def __init__(self, values=None):
            self._values = values or []

        def explist(self):
            return FakeExpList(self._values)

        def tableconstructor(self):
            return None

        def string(self):
            return None

    first_exp = SimpleNamespace(name="first")
    second_exp = SimpleNamespace(name="second")
    args_list = [FakeArgs([first_exp]), FakeArgs([second_exp])]

    class FakeCtx:
        def args(self):
            return args_list

        def getChildCount(self):
            return 2

        def getChild(self, index):
            return [args_list[0], args_list[1]][index]

    visitor._parse_expression = lambda exp: exp.name

    assert visitor._extract_arguments(FakeCtx()) == ["first", "second"]


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


def test_extract_literal_value_numbers_bool_nil_and_default():
    visitor = TactusDSLVisitor()

    class FakeNumber:
        def __init__(self, int_token=None, float_token=None):
            self._int_token = int_token
            self._float_token = float_token

        def INT(self):
            return self._int_token

        def FLOAT(self):
            return self._float_token

    class FakeExp:
        def __init__(self, text, number_ctx=None):
            self._text = text
            self._number_ctx = number_ctx

        def string(self):
            return None

        def number(self):
            return self._number_ctx

        def getText(self):
            return self._text

    int_token = SimpleNamespace(getText=lambda: "12")
    float_token = SimpleNamespace(getText=lambda: "1.5")

    assert visitor._extract_literal_value(FakeExp("12", FakeNumber(int_token=int_token))) == 12
    assert (
        visitor._extract_literal_value(FakeExp("1.5", FakeNumber(float_token=float_token))) == 1.5
    )
    assert visitor._extract_literal_value(FakeExp("true")) is True
    assert visitor._extract_literal_value(FakeExp("false")) is False
    assert visitor._extract_literal_value(FakeExp("nil")) is None
    assert visitor._extract_literal_value(FakeExp("value")) == "value"


def test_extract_function_name_from_terminal_and_var():
    visitor = TactusDSLVisitor()

    class FakeTerminal:
        def __init__(self, text):
            self.symbol = object()
            self._text = text

        def getText(self):
            return self._text

    class FakeVar:
        def NAME(self):
            return SimpleNamespace(getText=lambda: "fallback")

    class FakeVarOrExp:
        def var(self):
            return FakeVar()

    class FakeCtx:
        def __init__(self, children, var_or_exp):
            self._children = children
            self._var_or_exp = var_or_exp

        def getChildCount(self):
            return len(self._children)

        def getChild(self, idx):
            return self._children[idx]

        def varOrExp(self):
            return self._var_or_exp

    ctx = FakeCtx([FakeTerminal("Name")], FakeVarOrExp())
    assert visitor._extract_function_name(ctx) == "Name"

    ctx = FakeCtx([SimpleNamespace(getText=lambda: "1")], FakeVarOrExp())
    assert visitor._extract_function_name(ctx) == "fallback"


def test_extract_single_table_arg_handles_missing_table():  # noqa: F811
    visitor = TactusDSLVisitor()

    class FakeArgsCtx:
        def tableconstructor(self):
            return None

    class FakeCall:
        def __init__(self, args):
            self._args = args

        def args(self):
            return self._args

    assert visitor._extract_single_table_arg(FakeCall([])) == {}
    assert visitor._extract_single_table_arg(FakeCall([FakeArgsCtx()])) == {}


def test_process_dsl_call_procedure_variants():
    visitor = TactusDSLVisitor()
    visitor.builder = SimpleNamespace(
        register_named_procedure=lambda *_args, **_kwargs: None,
        register_input_schema=lambda *_args, **_kwargs: None,
        register_output_schema=lambda *_args, **_kwargs: None,
        register_state_schema=lambda *_args, **_kwargs: None,
    )

    visitor._extract_arguments = lambda _ctx: [{"input": {"name": {}}, "state": {"x": {}}}]
    visitor._process_dsl_call("Procedure", SimpleNamespace())


def test_parse_table_constructor_old_type_syntax_error():
    visitor = TactusDSLVisitor()

    class FakeStringCtx:
        def NORMALSTRING(self):
            return SimpleNamespace(getText=lambda: '"string"')

        def CHARSTRING(self):
            return None

        def LONGSTRING(self):
            return None

    class FakeExp:
        def number(self):
            return None

        def string(self):
            return FakeStringCtx()

        def NIL(self):
            return None

        def FALSE(self):
            return None

        def TRUE(self):
            return None

        def tableconstructor(self):
            return None

        def prefixexp(self):
            return None

        def getText(self):
            return "string"

    class FakeField:
        def __init__(self):
            self.start = SimpleNamespace(line=1, column=2)

        def NAME(self):
            return SimpleNamespace(getText=lambda: "type")

        def exp(self, idx=None):
            return FakeExp()

    class FakeFieldlist:
        def field(self):
            return [FakeField()]

    class FakeCtx:
        def fieldlist(self):
            return FakeFieldlist()

        def getText(self):
            return "type='string', required=true"

    visitor._parse_table_constructor(FakeCtx())
    assert any("Old type syntax detected" in err.message for err in visitor.errors)

    visitor._extract_arguments = lambda _ctx: [[]]
    visitor._process_dsl_call("Procedure", SimpleNamespace())

    visitor._extract_arguments = lambda _ctx: ["named", {"output": {"ok": {}}}]
    visitor._process_dsl_call("Procedure", SimpleNamespace())


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


def test_parse_expression_field_builder_options():
    visitor = TactusDSLVisitor()

    class FakeArgs:
        def __init__(self, table):
            self._table = table

        def tableconstructor(self):
            return self._table

    class FakeFuncCall:
        def NAME(self):
            return [
                SimpleNamespace(getText=lambda: "field"),
                SimpleNamespace(getText=lambda: "string"),
            ]

        def args(self, idx=None):
            args_list = [FakeArgs(SimpleNamespace())]
            if idx is None:
                return args_list
            return args_list[idx]

    class FakePrefix:
        def functioncall(self):
            return FakeFuncCall()

    class FakeExp:
        def prefixexp(self):
            return FakePrefix()

        def number(self):
            return None

        def string(self):
            return None

    visitor._parse_table_constructor = lambda _ctx: {
        "required": False,
        "default": "x",
        "description": "desc",
        "enum": ["a", "b"],
    }

    field_def = visitor._parse_expression(FakeExp())
    assert field_def["type"] == "string"
    assert field_def["default"] == "x"
    assert field_def["description"] == "desc"
    assert field_def["enum"] == ["a", "b"]


def test_parse_expression_field_builder_without_table_options():
    visitor = TactusDSLVisitor()

    class FakeArgs:
        def __init__(self):
            self._table = None

        def tableconstructor(self):
            return None

    class FakeFuncCall:
        def NAME(self):
            return [
                SimpleNamespace(getText=lambda: "field"),
                SimpleNamespace(getText=lambda: "number"),
            ]

        def args(self, idx=None):
            args_list = [FakeArgs()]
            if idx is None:
                return args_list
            return args_list[idx]

    class FakePrefix:
        def functioncall(self):
            return FakeFuncCall()

    class FakeExp:
        def prefixexp(self):
            return FakePrefix()

        def number(self):
            return None

        def string(self):
            return None

    field_def = visitor._parse_expression(FakeExp())
    assert field_def["type"] == "number"
    assert field_def["required"] is False


def test_parse_expression_field_builder_required_skips_default():
    visitor = TactusDSLVisitor()

    class FakeArgs:
        def __init__(self, table):
            self._table = table

        def tableconstructor(self):
            return self._table

    class FakeFuncCall:
        def NAME(self):
            return [
                SimpleNamespace(getText=lambda: "field"),
                SimpleNamespace(getText=lambda: "string"),
            ]

        def args(self, idx=None):
            args_list = [FakeArgs(SimpleNamespace())]
            if idx is None:
                return args_list
            return args_list[idx]

    class FakePrefix:
        def functioncall(self):
            return FakeFuncCall()

    class FakeExp:
        def prefixexp(self):
            return FakePrefix()

        def number(self):
            return None

        def string(self):
            return None

    visitor._parse_table_constructor = lambda _ctx: {"required": True, "default": "x"}
    field_def = visitor._parse_expression(FakeExp())
    assert "default" not in field_def


def test_visit_functioncall_processes_dsl_call():
    calls = {}

    class Visitor(TactusDSLVisitor):
        def visitChildren(self, ctx):
            return "visited"

    visitor = Visitor()
    visitor._extract_function_name = lambda _ctx: "Model"

    def fake_process(name, _ctx):
        calls["name"] = name

    visitor._process_dsl_call = fake_process

    class FakeStart:
        line = 1
        column = 2

    class FakeCtx:
        start = FakeStart()

        def getText(self):
            return "Model()"

    assert visitor.visitFunctioncall(FakeCtx()) == "visited"
    assert calls["name"] == "Model"


def test_parse_table_constructor_array_items_and_json_schema_skip():
    visitor = TactusDSLVisitor()

    class FakeStringCtx:
        def __init__(self, text):
            self._text = text

        def NORMALSTRING(self):
            return SimpleNamespace(getText=lambda: self._text)

        def CHARSTRING(self):
            return None

        def LONGSTRING(self):
            return None

    class FakeExp:
        def __init__(self, text):
            self._text = text

        def number(self):
            return None

        def string(self):
            if self._text.startswith('"') and self._text.endswith('"'):
                return FakeStringCtx(self._text)
            return None

        def NIL(self):
            return None

        def FALSE(self):
            return None

        def TRUE(self):
            return None

        def tableconstructor(self):
            return None

        def prefixexp(self):
            return None

        def getText(self):
            return self._text

    class FakeField:
        def __init__(self, name=None, exp=None):
            self._name = name
            self._exp = exp
            self.start = SimpleNamespace(line=1, column=2)

        def NAME(self):
            if self._name is None:
                return None
            return SimpleNamespace(getText=lambda: self._name)

        def exp(self, idx=None):
            if idx is None:
                return [self._exp] if self._exp is not None else []
            return self._exp

    class FakeFieldlist:
        def __init__(self, fields):
            self._fields = fields

        def field(self):
            return self._fields

    class FakeCtx:
        def __init__(self, text, fields):
            self._text = text
            self._fields = fields

        def fieldlist(self):
            return FakeFieldlist(self._fields)

        def getText(self):
            return self._text

    fields = [
        FakeField(name="type", exp=FakeExp('"string"')),
        FakeField(exp=FakeExp('"item"')),
    ]
    ctx = FakeCtx('json_schema={type="string",required=true}', fields)
    result = visitor._parse_table_constructor(ctx)

    assert result[1] == "item"
    assert not any("Old type syntax detected" in err.message for err in visitor.errors)


def test_parse_table_constructor_indexed_field_is_skipped():
    visitor = TactusDSLVisitor()

    class FakeExp:
        def number(self):
            return None

        def string(self):
            return None

        def NIL(self):
            return None

        def FALSE(self):
            return None

        def TRUE(self):
            return None

        def tableconstructor(self):
            return None

        def prefixexp(self):
            return None

        def getText(self):
            return "1"

    class FakeField:
        def __init__(self):
            self.start = SimpleNamespace(line=1, column=2)

        def NAME(self):
            return None

        def exp(self, idx=None):
            if idx is None:
                return [FakeExp(), FakeExp()]
            return FakeExp()

    class FakeFieldlist:
        def field(self):
            return [FakeField()]

    class FakeCtx:
        def fieldlist(self):
            return FakeFieldlist()

        def getText(self):
            return "[1]='value'"

    result = visitor._parse_table_constructor(FakeCtx())
    assert result == []


def test_process_dsl_call_settings_and_model_variants():
    calls = {}

    class Builder:
        def set_async(self, value):
            calls["async"] = value

        def set_max_depth(self, value):
            calls["max_depth"] = value

        def set_max_turns(self, value):
            calls["max_turns"] = value

        def register_model(self, name, config):
            calls.setdefault("models", []).append((name, config))

    visitor = TactusDSLVisitor()
    visitor.builder = Builder()
    visitor._extract_arguments = lambda _ctx: ["value"]

    visitor._process_dsl_call("async", SimpleNamespace())
    visitor._process_dsl_call("max_depth", SimpleNamespace())
    visitor._process_dsl_call("max_turns", SimpleNamespace())

    assert calls["async"] == "value"
    assert calls["max_depth"] == "value"
    assert calls["max_turns"] == "value"

    visitor._extract_arguments = lambda _ctx: ["model_name"]
    visitor._process_dsl_call("Model", SimpleNamespace())
    assert calls["models"][-1] == ("model_name", {})


def test_process_dsl_call_input_output_tool_and_toolset():
    calls = {}

    class Builder:
        def register_top_level_input(self, schema):
            calls["input"] = schema

        def register_top_level_output(self, schema):
            calls["output"] = schema

        def register_toolset(self, name, config):
            calls["toolset"] = (name, config)

    visitor = TactusDSLVisitor()
    visitor.builder = Builder()

    visitor._extract_arguments = lambda _ctx: [{"field": {}}]
    visitor._process_dsl_call("input", SimpleNamespace())
    visitor._process_dsl_call("output", SimpleNamespace())
    assert calls["input"] == {"field": {}}
    assert calls["output"] == {"field": {}}

    visitor._extract_arguments = lambda _ctx: ["tool_name"]
    visitor._process_dsl_call("Tool", SimpleNamespace())
    assert any("Curried Tool syntax is not supported" in err.message for err in visitor.errors)

    visitor._extract_arguments = lambda _ctx: ["tools", {"items": []}]
    visitor._process_dsl_call("Toolset", SimpleNamespace())
    assert calls["toolset"][0] == "tools"


def test_process_dsl_call_skips_when_no_args():
    calls = {}

    class Builder:
        def set_max_depth(self, value):
            calls["max_depth"] = value

    visitor = TactusDSLVisitor()
    visitor.builder = Builder()
    visitor._extract_arguments = lambda _ctx: []

    visitor._process_dsl_call("max_depth", SimpleNamespace())
    assert "max_depth" not in calls


def test_visit_functioncall_handles_unexpected_exception():
    visitor = TactusDSLVisitor()

    class FakeCtx:
        start = None

        def getText(self):
            raise RuntimeError("boom")

    visitor.visitChildren = lambda _ctx: None
    visitor.visitFunctioncall(FakeCtx())


def test_extract_literal_value_charstring_single_quote():
    visitor = TactusDSLVisitor()

    class FakeStringCtx:
        def NORMALSTRING(self):
            return None

        def CHARSTRING(self):
            return SimpleNamespace(getText=lambda: "'hello'")

    class FakeExp:
        def string(self):
            return FakeStringCtx()

        def number(self):
            return None

        def getText(self):
            return "'hello'"

    assert visitor._extract_literal_value(FakeExp()) == "hello"


def test_visit_functioncall_method_access_with_colon_skips():
    class Visitor(TactusDSLVisitor):
        def visitChildren(self, ctx):
            return "visited"

    visitor = Visitor()

    class FakeStart:
        line = 1
        column = 2

    class FakeCtx:
        start = FakeStart()

        def getText(self):
            return "Tool:called()"

        def getChildCount(self):
            return 1

        def getChild(self, _index):
            return SimpleNamespace(symbol=object(), getText=lambda: "Tool")

        def varOrExp(self):
            return None

    assert visitor.visitFunctioncall(FakeCtx()) == "visited"


def test_extract_arguments_shorthand_without_method_chain():
    visitor = TactusDSLVisitor()

    class FakeExpList:
        def __init__(self, values):
            self._values = values

        def exp(self):
            return self._values

    class FakeArgs:
        def __init__(self, values=None):
            self._values = values or []

        def explist(self):
            return FakeExpList(self._values)

        def tableconstructor(self):
            return None

        def string(self):
            return None

    first_exp = SimpleNamespace(name="first")
    second_exp = SimpleNamespace(name="second")
    args_list = [FakeArgs([first_exp]), FakeArgs([second_exp])]

    class FakeCtx:
        def args(self):
            return args_list

        def getChildCount(self):
            return 2

        def getChild(self, index):
            return [args_list[0], args_list[1]][index]

    visitor._parse_expression = lambda exp: exp.name

    assert visitor._extract_arguments(FakeCtx()) == ["first", "second"]


def test_parse_expression_field_builder_options_non_dict():
    visitor = TactusDSLVisitor()

    class FakeArgs:
        def tableconstructor(self):
            return SimpleNamespace()

    class FakeFuncCall:
        def NAME(self):
            return [
                SimpleNamespace(getText=lambda: "field"),
                SimpleNamespace(getText=lambda: "string"),
            ]

        def args(self, *_args):
            return FakeArgs()

    class FakePrefix:
        def functioncall(self):
            return FakeFuncCall()

    class FakeExp:
        def prefixexp(self):
            return FakePrefix()

        def number(self):
            return None

        def string(self):
            return None

        def NIL(self):
            return None

        def FALSE(self):
            return None

        def TRUE(self):
            return None

        def tableconstructor(self):
            return None

    visitor._parse_table_constructor = lambda _ctx: ["not-a-dict"]
    field_def = visitor._parse_expression(FakeExp())

    assert field_def["type"] == "string"
    assert field_def["required"] is False
    assert "default" not in field_def


def test_process_dsl_call_async_without_args():
    calls = {}

    class Builder:
        def set_async(self, value):
            calls["async"] = value

    visitor = TactusDSLVisitor()
    visitor.builder = Builder()
    visitor._extract_arguments = lambda _ctx: []

    visitor._process_dsl_call("async", SimpleNamespace())
    assert "async" not in calls


def test_visit_stat_assigns_max_turns():
    calls = {}

    class Builder:
        def __getattr__(self, name):
            if name.startswith("set_"):
                return lambda *_args, **_kwargs: None
            raise AttributeError(name)

        def set_max_turns(self, value):
            calls["max_turns"] = value

    class Visitor(TactusDSLVisitor):
        def visitChildren(self, ctx):
            return "visited"

    visitor = Visitor()
    visitor.builder = Builder()
    visitor._extract_literal_value = lambda _exp: 7

    class FakeVar:
        def NAME(self):
            return SimpleNamespace(getText=lambda: "max_turns")

    class FakeVarlist:
        def var(self):
            return [FakeVar()]

    class FakeExplist:
        def exp(self):
            return [SimpleNamespace()]

    class FakeCtx:
        def varlist(self):
            return FakeVarlist()

        def explist(self):
            return FakeExplist()

    assert visitor.visitStat(FakeCtx()) == "visited"
    assert calls["max_turns"] == 7


def test_check_assignment_based_declaration_tools_non_list():
    calls = {}

    class Builder:
        def register_agent(self, name, config, _ctx):
            calls["agent"] = (name, config)

    visitor = TactusDSLVisitor()
    visitor.builder = Builder()
    visitor._extract_function_name = lambda _ctx: "Agent"
    visitor._extract_single_table_arg = lambda _ctx: {"tools": "not-a-list"}

    class FakeFuncCall:
        def getChildCount(self):
            return 1

    class FakePrefixExp:
        def functioncall(self):
            return FakeFuncCall()

    class FakeExp:
        def prefixexp(self):
            return FakePrefixExp()

    visitor._check_assignment_based_declaration("greeter", FakeExp())
    assert calls["agent"][1]["tools"] == "not-a-list"


def test_extract_single_table_arg_with_non_table_args():
    visitor = TactusDSLVisitor()

    class FakeArgs:
        def tableconstructor(self):
            return None

    class FakeFuncCall:
        def args(self):
            return [FakeArgs()]

    assert visitor._extract_single_table_arg(FakeFuncCall()) == {}


def test_visit_functioncall_invokes_process_dsl_call():
    called = {}

    class Visitor(TactusDSLVisitor):
        def visitChildren(self, ctx):
            return "visited"

    visitor = Visitor()

    class FakeStart:
        line = 1
        column = 2

    class FakeCtx:
        start = FakeStart()

        def getText(self):
            return "Tool()"

        def getChildCount(self):
            return 1

        def getChild(self, _index):
            return SimpleNamespace(symbol=object(), getText=lambda: "Tool")

        def varOrExp(self):
            return None

    visitor._process_dsl_call = lambda name, _ctx: called.setdefault("name", name)
    assert visitor.visitFunctioncall(FakeCtx()) == "visited"
    assert called["name"] == "Tool"


def test_process_dsl_call_model_name_only():  # noqa: F811
    calls = {}

    class Builder:
        def register_model(self, name, config):
            calls["model"] = (name, config)

    visitor = TactusDSLVisitor()
    visitor.builder = Builder()
    visitor._extract_arguments = lambda _ctx: ["model_name"]

    visitor._process_dsl_call("Model", SimpleNamespace())
    assert calls["model"] == ("model_name", {})


def test_process_dsl_call_max_turns_with_args():
    calls = {}

    class Builder:
        def set_max_turns(self, value):
            calls["max_turns"] = value

    visitor = TactusDSLVisitor()
    visitor.builder = Builder()
    visitor._extract_arguments = lambda _ctx: [3]

    visitor._process_dsl_call("max_turns", SimpleNamespace())
    assert calls["max_turns"] == 3


def test_process_dsl_call_max_turns_without_args():
    calls = {}

    class Builder:
        def set_max_turns(self, value):
            calls["max_turns"] = value

    visitor = TactusDSLVisitor()
    visitor.builder = Builder()
    visitor._extract_arguments = lambda _ctx: []

    visitor._process_dsl_call("max_turns", SimpleNamespace())
    assert "max_turns" not in calls


def test_process_dsl_call_output_non_dict():
    calls = {}

    class Builder:
        def register_top_level_output(self, schema):
            calls["output"] = schema

    visitor = TactusDSLVisitor()
    visitor.builder = Builder()
    visitor._extract_arguments = lambda _ctx: ["not-a-dict"]

    visitor._process_dsl_call("output", SimpleNamespace())
    assert "output" not in calls


def test_process_dsl_call_tool_non_string_arg():
    visitor = TactusDSLVisitor()
    visitor._extract_arguments = lambda _ctx: [{"name": "x"}]

    visitor._process_dsl_call("Tool", SimpleNamespace())
    assert visitor.errors == []


def test_process_dsl_call_toolset_without_args():
    calls = {}

    class Builder:
        def register_toolset(self, name, config):
            calls["toolset"] = (name, config)

    visitor = TactusDSLVisitor()
    visitor.builder = Builder()
    visitor._extract_arguments = lambda _ctx: []

    visitor._process_dsl_call("Toolset", SimpleNamespace())
    assert "toolset" not in calls


def test_process_dsl_call_unknown_noop():
    visitor = TactusDSLVisitor()
    visitor._extract_arguments = lambda _ctx: []

    visitor._process_dsl_call("UnknownCall", SimpleNamespace())
    assert visitor.errors == []


def test_process_dsl_call_output_with_args():
    calls = {}

    class Builder:
        def register_top_level_output(self, schema):
            calls["output"] = schema

    visitor = TactusDSLVisitor()
    visitor.builder = Builder()
    visitor._extract_arguments = lambda _ctx: [{"field": {}}]

    visitor._process_dsl_call("output", SimpleNamespace())
    assert calls["output"] == {"field": {}}


def test_visit_stat_sets_max_turns():
    class FakeBuilder:
        def __init__(self):
            self.max_turns = None

        def __getattr__(self, name):
            if name.startswith("set_"):
                return lambda *_args, **_kwargs: None
            raise AttributeError(name)

        def set_max_turns(self, value):
            self.max_turns = value

    visitor = TactusDSLVisitor()
    visitor.builder = FakeBuilder()
    visitor.visitChildren = lambda _ctx: None

    class FakeNumberCtx:
        def INT(self):
            return SimpleNamespace(getText=lambda: "5")

        def FLOAT(self):
            return None

    class FakeExp:
        def string(self):
            return None

        def number(self):
            return FakeNumberCtx()

        def getText(self):
            return "5"

    class FakeExplist:
        def exp(self):
            return [FakeExp()]

    class FakeVar:
        def NAME(self):
            return SimpleNamespace(getText=lambda: "max_turns")

    class FakeVarlist:
        def var(self):
            return [FakeVar()]

    class FakeCtx:
        def varlist(self):
            return FakeVarlist()

        def explist(self):
            return FakeExplist()

    visitor.visitStat(FakeCtx())
    assert visitor.builder.max_turns == 5


def test_extract_single_table_arg_non_table_returns_empty():
    visitor = TactusDSLVisitor()

    class FakeArgs:
        def tableconstructor(self):
            return None

    class FakeFuncCall:
        def args(self):
            return [FakeArgs()]

    assert visitor._extract_single_table_arg(FakeFuncCall()) == {}


def test_visit_functioncall_skips_method_call():  # noqa: F811
    called = {"dsl": False}

    class Visitor(TactusDSLVisitor):
        def _extract_function_name(self, _ctx):
            return "Tool"

        def _process_dsl_call(self, _name, _ctx):
            called["dsl"] = True

    class FakeCtx:
        start = SimpleNamespace(line=1, column=2)

        def getText(self):
            return "Tool.called()"

    visitor = Visitor()
    visitor.visitChildren = lambda _ctx: None
    visitor.visitFunctioncall(FakeCtx())

    assert called["dsl"] is False


def test_extract_arguments_method_chain_only_first_args():
    visitor = TactusDSLVisitor()
    visitor._parse_expression = lambda exp: exp.name

    class FakeExp:
        def __init__(self, name):
            self.name = name

        def prefixexp(self):
            return None

        def number(self):
            return None

        def string(self):
            return None

        def NIL(self):
            return None

        def FALSE(self):
            return None

        def TRUE(self):
            return None

        def tableconstructor(self):
            return None

    class FakeExplist:
        def __init__(self, exps):
            self._exps = exps

        def exp(self):
            return self._exps

    class FakeArgs:
        def __init__(self, exps):
            self._explist = FakeExplist(exps)

        def explist(self):
            return self._explist

        def tableconstructor(self):
            return None

        def string(self):
            return None

    arg1 = FakeArgs([FakeExp("first")])
    arg2 = FakeArgs([FakeExp("second")])

    class DotToken:
        symbol = object()

        def getText(self):
            return "."

    class FakeCtx:
        def args(self):
            return [arg1, arg2]

        def getChildCount(self):
            return 3

        def getChild(self, idx):
            return [arg1, DotToken(), arg2][idx]

    assert visitor._extract_arguments(FakeCtx()) == ["first"]


def test_process_dsl_call_model_name_only_registers():
    visitor = TactusDSLVisitor()

    class FakeBuilder:
        def __init__(self):
            self.calls = []

        def register_model(self, name, config):
            self.calls.append((name, config))

    visitor.builder = FakeBuilder()
    visitor._extract_arguments = lambda _ctx: ["demo-model"]

    visitor._process_dsl_call("Model", SimpleNamespace())

    assert visitor.builder.calls == [("demo-model", {})]


def test_process_dsl_call_toolset_registers():  # noqa: F811
    visitor = TactusDSLVisitor()

    class FakeBuilder:
        def __init__(self):
            self.calls = []

        def register_toolset(self, name, config):
            self.calls.append((name, config))

    visitor.builder = FakeBuilder()
    visitor._extract_arguments = lambda _ctx: ["tools"]

    visitor._process_dsl_call("Toolset", SimpleNamespace())

    assert visitor.builder.calls == [("tools", {})]


def test_parse_table_constructor_array_only_returns_list():
    visitor = TactusDSLVisitor()
    visitor._parse_expression = lambda _ctx: "item"

    class FakeField:
        def __init__(self):
            self.start = SimpleNamespace(line=1, column=2)

        def NAME(self):
            return None

        def exp(self, idx=None):
            if idx is None:
                return [SimpleNamespace()]
            return SimpleNamespace()

    class FakeFieldlist:
        def field(self):
            return [FakeField()]

    class FakeCtx:
        def fieldlist(self):
            return FakeFieldlist()

        def getText(self):
            return "{'a'}"

    assert visitor._parse_table_constructor(FakeCtx()) == ["item"]


def test_visit_stat_calls_assignment_declaration():
    visitor = TactusDSLVisitor()
    visitor.visitChildren = lambda _ctx: None
    called = {"value": None}
    visitor._check_assignment_based_declaration = lambda name, _exp: called.update({"value": name})

    class FakeExp:
        def prefixexp(self):
            return None

    class FakeExplist:
        def exp(self):
            return [FakeExp()]

    class FakeVar:
        def NAME(self):
            return SimpleNamespace(getText=lambda: "greeter")

    class FakeVarlist:
        def var(self):
            return [FakeVar()]

    class FakeCtx:
        def varlist(self):
            return FakeVarlist()

        def explist(self):
            return FakeExplist()

    visitor.visitStat(FakeCtx())
    assert called["value"] == "greeter"


def test_visit_functioncall_with_no_name_skips_processing():
    called = {"dsl": False}

    class Visitor(TactusDSLVisitor):
        def _extract_function_name(self, _ctx):
            return None

        def _process_dsl_call(self, _name, _ctx):
            called["dsl"] = True

    class FakeCtx:
        start = SimpleNamespace(line=1, column=2)

        def getText(self):
            return "Tool()"

    visitor = Visitor()
    visitor.visitChildren = lambda _ctx: None
    visitor.visitFunctioncall(FakeCtx())

    assert called["dsl"] is False


def test_extract_arguments_non_method_chain_uses_all_args():
    visitor = TactusDSLVisitor()
    visitor._parse_expression = lambda exp: exp.name

    class FakeExp:
        def __init__(self, name):
            self.name = name

        def prefixexp(self):
            return None

        def number(self):
            return None

        def string(self):
            return None

        def NIL(self):
            return None

        def FALSE(self):
            return None

        def TRUE(self):
            return None

        def tableconstructor(self):
            return None

    class FakeExplist:
        def __init__(self, exps):
            self._exps = exps

        def exp(self):
            return self._exps

    class FakeArgs:
        def __init__(self, exps):
            self._explist = FakeExplist(exps)

        def explist(self):
            return self._explist

        def tableconstructor(self):
            return None

        def string(self):
            return None

    arg1 = FakeArgs([FakeExp("first")])
    arg2 = FakeArgs([FakeExp("second")])

    class FakeCtx:
        def args(self):
            return [arg1, arg2]

        def getChildCount(self):
            return 2

        def getChild(self, idx):
            return [arg1, arg2][idx]

    assert visitor._extract_arguments(FakeCtx()) == ["first", "second"]


def test_extract_literal_value_charstring_single_quote():  # noqa: F811
    visitor = TactusDSLVisitor()

    class FakeStringCtx:
        def NORMALSTRING(self):
            return None

        def CHARSTRING(self):
            return SimpleNamespace(getText=lambda: "'hi'")

    class FakeExp:
        def string(self):
            return FakeStringCtx()

        def number(self):
            return None

        def getText(self):
            return "'hi'"

    assert visitor._extract_literal_value(FakeExp()) == "hi"


def test_extract_literal_value_unquoted_normalstring():
    visitor = TactusDSLVisitor()

    class FakeStringCtx:
        def NORMALSTRING(self):
            return SimpleNamespace(getText=lambda: "hi")

        def CHARSTRING(self):
            return None

    class FakeExp:
        def string(self):
            return FakeStringCtx()

        def number(self):
            return None

        def getText(self):
            return "hi"

    assert visitor._extract_literal_value(FakeExp()) == "hi"


def test_extract_single_table_arg_non_table():
    visitor = TactusDSLVisitor()

    class FakeArgs:
        def tableconstructor(self):
            return None

    class FakeFuncCall:
        def args(self):
            return [FakeArgs()]

    assert visitor._extract_single_table_arg(FakeFuncCall()) == {}


def test_extract_arguments_method_chain_skips_second_args():
    visitor = TactusDSLVisitor()

    class FakeString:
        def NORMALSTRING(self):
            return SimpleNamespace(getText=lambda: '"one"')

        def CHARSTRING(self):
            return None

        def LONGSTRING(self):
            return None

    class FakeArgs:
        def explist(self):
            return None

        def tableconstructor(self):
            return None

        def string(self):
            return FakeString()

    arg1 = FakeArgs()
    arg2 = FakeArgs()

    class DotChild:
        symbol = object()

        def getText(self):
            return "."

    class FakeCtx:
        def args(self):
            return [arg1, arg2]

        def getChildCount(self):
            return 3

        def getChild(self, idx):
            return [arg1, DotChild(), arg2][idx]

    assert visitor._extract_arguments(FakeCtx()) == ["one"]


def test_parse_expression_field_builder_with_options():  # noqa: F811
    visitor = TactusDSLVisitor()

    visitor._parse_table_constructor = lambda _ctx: {
        "required": False,
        "default": "x",
        "description": "desc",
        "enum": ["a", "b"],
    }

    class FakeArgs:
        def tableconstructor(self):
            return object()

    class FakeFuncCall:
        def NAME(self):
            return [
                SimpleNamespace(getText=lambda: "field"),
                SimpleNamespace(getText=lambda: "string"),
            ]

        def args(self, index=None):
            return [FakeArgs()] if index is None else FakeArgs()

    class FakePrefix:
        def functioncall(self):
            return FakeFuncCall()

    class FakeExp:
        def prefixexp(self):
            return FakePrefix()

        def number(self):
            return None

        def string(self):
            return None

        def NIL(self):
            return None

        def FALSE(self):
            return None

        def TRUE(self):
            return None

        def tableconstructor(self):
            return None

    result = visitor._parse_expression(FakeExp())
    assert result["type"] == "string"
    assert result["default"] == "x"
    assert result["description"] == "desc"
    assert result["enum"] == ["a", "b"]


def test_parse_table_constructor_array_items():
    visitor = TactusDSLVisitor()
    visitor._parse_expression = lambda _exp: "item"

    class FakeField:
        def NAME(self):
            return None

        def exp(self, _index=None):
            return [object()]

    class FakeFieldList:
        def field(self):
            return [FakeField()]

    class FakeCtx:
        def fieldlist(self):
            return FakeFieldList()

    assert visitor._parse_table_constructor(FakeCtx()) == ["item"]


def test_process_dsl_call_tool_curried_records_error():
    visitor = TactusDSLVisitor()
    visitor.builder = SimpleNamespace(register_toolset=lambda *_args, **_kwargs: None)

    class FakeString:
        def NORMALSTRING(self):
            return SimpleNamespace(getText=lambda: '"tool"')

        def CHARSTRING(self):
            return None

        def LONGSTRING(self):
            return None

    class FakeArgs:
        def explist(self):
            return None

        def tableconstructor(self):
            return None

        def string(self):
            return FakeString()

    class FakeCtx:
        def args(self):
            return [FakeArgs()]

        def getChildCount(self):
            return 1

        def getChild(self, _idx):
            return self.args()[0]

    visitor._process_dsl_call("Tool", FakeCtx())
    assert visitor.errors


def test_extract_literal_value_charstring_unquoted():
    visitor = TactusDSLVisitor()

    class FakeStringCtx:
        def NORMALSTRING(self):
            return None

        def CHARSTRING(self):
            return SimpleNamespace(getText=lambda: "hi")

    class FakeExp:
        def string(self):
            return FakeStringCtx()

        def number(self):
            return None

        def getText(self):
            return "hi"

    assert visitor._extract_literal_value(FakeExp()) == "hi"


def test_extract_arguments_non_method_chain_uses_all_args_explicit():
    visitor = TactusDSLVisitor()

    class FakeString:
        def NORMALSTRING(self):
            return SimpleNamespace(getText=lambda: '"one"')

        def CHARSTRING(self):
            return None

        def LONGSTRING(self):
            return None

    class FakeArgs:
        def explist(self):
            return None

        def tableconstructor(self):
            return None

        def string(self):
            return FakeString()

    arg1 = FakeArgs()
    arg2 = FakeArgs()

    class FakeCtx:
        def args(self):
            return [arg1, arg2]

        def getChildCount(self):
            return 2

        def getChild(self, idx):
            return [arg1, arg2][idx]

    assert visitor._extract_arguments(FakeCtx()) == ["one", "one"]


def test_process_dsl_call_model_name_only_branch():
    visitor = TactusDSLVisitor()

    called = {}

    class DummyBuilder:
        def register_model(self, name, config):
            called["name"] = name
            called["config"] = config

    visitor.builder = DummyBuilder()
    visitor._extract_arguments = lambda _ctx: ["model_name"]

    visitor._process_dsl_call("Model", SimpleNamespace())

    assert called["name"] == "model_name"
    assert called["config"] == {}


def test_process_dsl_call_tool_curried_branch():
    visitor = TactusDSLVisitor()
    visitor._extract_arguments = lambda _ctx: ["tool_name"]

    visitor._process_dsl_call("Tool", SimpleNamespace())

    assert visitor.errors


def test_parse_expression_field_builder_without_table_options():  # noqa: F811
    visitor = TactusDSLVisitor()

    class FakeArgs:
        def tableconstructor(self):
            return None

    class FakeFuncCall:
        def NAME(self):
            return [
                SimpleNamespace(getText=lambda: "field"),
                SimpleNamespace(getText=lambda: "string"),
            ]

        def args(self, index=None):
            return [FakeArgs()] if index is None else FakeArgs()

    class FakePrefix:
        def functioncall(self):
            return FakeFuncCall()

    class FakeExp:
        def prefixexp(self):
            return FakePrefix()

        def number(self):
            return None

        def string(self):
            return None

        def NIL(self):
            return None

        def FALSE(self):
            return None

        def TRUE(self):
            return None

        def tableconstructor(self):
            return None

    result = visitor._parse_expression(FakeExp())
    assert result["type"] == "string"


def test_visit_stat_sets_max_turns_branch():
    visitor = TactusDSLVisitor()

    class DummyBuilder:
        def __init__(self):
            self.max_turns = None

        def __getattr__(self, name):
            if name.startswith("set_"):
                return lambda *_args, **_kwargs: None
            raise AttributeError(name)

        def set_max_turns(self, value):
            self.max_turns = value

    visitor.builder = DummyBuilder()

    class FakeVar:
        def NAME(self):
            return SimpleNamespace(getText=lambda: "max_turns")

    class FakeVarList:
        def var(self):
            return [FakeVar()]

    class FakeNumber:
        def INT(self):
            return SimpleNamespace(getText=lambda: "9")

        def FLOAT(self):
            return None

    class FakeExp:
        def string(self):
            return None

        def number(self):
            return FakeNumber()

        def getText(self):
            return "9"

    class FakeExplist:
        def exp(self):
            return [FakeExp()]

    class FakeCtx:
        def varlist(self):
            return FakeVarList()

        def explist(self):
            return FakeExplist()

        def getChildCount(self):
            return 0

        def getChild(self, _index):
            return None

    visitor.visitStat(FakeCtx())
    assert visitor.builder.max_turns == 9


def test_visit_stat_setting_missing_expression_skips():
    visitor = TactusDSLVisitor()

    class DummyBuilder:
        def __init__(self):
            self.max_turns = None

        def __getattr__(self, name):
            if name.startswith("set_"):
                return lambda *_args, **_kwargs: None
            raise AttributeError(name)

        def set_max_turns(self, value):
            self.max_turns = value

    visitor.builder = DummyBuilder()

    class FakeVar:
        def NAME(self):
            return SimpleNamespace(getText=lambda: "max_turns")

    class FakeVarList:
        def var(self):
            return [FakeVar()]

    class FakeExplist:
        def exp(self):
            return []

    class FakeCtx:
        def varlist(self):
            return FakeVarList()

        def explist(self):
            return FakeExplist()

        def getChildCount(self):
            return 0

        def getChild(self, _index):
            return None

    visitor.visitStat(FakeCtx())
    assert visitor.builder.max_turns is None


def test_visit_stat_assignment_based_declaration_calls_checker():
    visitor = TactusDSLVisitor()
    called = {}

    def fake_check(name, exp):
        called["name"] = name
        called["exp"] = exp

    visitor._check_assignment_based_declaration = fake_check

    class FakeVar:
        def NAME(self):
            return SimpleNamespace(getText=lambda: "greeter")

    class FakeVarList:
        def var(self):
            return [FakeVar()]

    class FakeExplist:
        def exp(self):
            return [SimpleNamespace()]

    class FakeCtx:
        def varlist(self):
            return FakeVarList()

        def explist(self):
            return FakeExplist()

        def getChildCount(self):
            return 0

        def getChild(self, _index):
            return None

    visitor.visitStat(FakeCtx())
    assert called["name"] == "greeter"


def test_extract_single_table_arg_empty_args_returns_empty():
    visitor = TactusDSLVisitor()

    class FakeFuncCall:
        def args(self, _index=None):
            return []

    assert visitor._extract_single_table_arg(FakeFuncCall()) == {}


def test_extract_single_table_arg_without_table_returns_empty():  # noqa: F811
    visitor = TactusDSLVisitor()

    class FakeArgs:
        def tableconstructor(self):
            return None

    class FakeFuncCall:
        def args(self, _index=None):
            return [FakeArgs()]

    assert visitor._extract_single_table_arg(FakeFuncCall()) == {}


def test_extract_literal_value_charstring_unquoted_returns_text():
    visitor = TactusDSLVisitor()

    class FakeString:
        def NORMALSTRING(self):
            return None

        def CHARSTRING(self):
            return SimpleNamespace(getText=lambda: "abc")

    class FakeExp:
        def prefixexp(self):
            return None

        def string(self):
            return FakeString()

        def number(self):
            return None

        def getText(self):
            return "abc"

    assert visitor._extract_literal_value(FakeExp()) == "abc"


def test_extract_literal_value_string_without_tokens_falls_through_to_number():
    visitor = TactusDSLVisitor()

    class FakeString:
        def NORMALSTRING(self):
            return None

        def CHARSTRING(self):
            return None

    class FakeNumber:
        def INT(self):
            return SimpleNamespace(getText=lambda: "11")

        def FLOAT(self):
            return None

        def getText(self):
            return "11"

    class FakeExp:
        def prefixexp(self):
            return None

        def string(self):
            return FakeString()

        def number(self):
            return FakeNumber()

        def getText(self):
            return "11"

    assert visitor._extract_literal_value(FakeExp()) == 11


def test_visit_functioncall_model_name_only_registers_empty_config():
    visitor = TactusDSLVisitor()

    class DummyBuilder:
        def __init__(self):
            self.models = {}

        def register_model(self, name, config):
            self.models[name] = config

    visitor.builder = DummyBuilder()

    class FakeString:
        def NORMALSTRING(self):
            return SimpleNamespace(getText=lambda: '"demo"')

        def CHARSTRING(self):
            return None

    class FakeExp:
        def prefixexp(self):
            return None

        def string(self):
            return FakeString()

        def number(self):
            return None

        def NIL(self):
            return None

        def FALSE(self):
            return None

        def TRUE(self):
            return None

        def tableconstructor(self):
            return None

        def getText(self):
            return '"demo"'

    class FakeExplist:
        def exp(self):
            return [FakeExp()]

    class FakeArgs:
        def explist(self):
            return FakeExplist()

        def tableconstructor(self):
            return None

    class FakeChild:
        symbol = object()

        def getText(self):
            return "Model"

        def accept(self, _visitor):
            return None

    class FakeCtx:
        start = None

        def getChildCount(self):
            return 1

        def getChild(self, _index):
            return FakeChild()

        def varOrExp(self):
            return None

        def args(self):
            return [FakeArgs()]

        def getText(self):
            return 'Model("demo")'

    visitor.visitFunctioncall(FakeCtx())
    assert visitor.builder.models["demo"] == {}


def test_visit_functioncall_model_non_string_args_skips_registration():
    visitor = TactusDSLVisitor()

    class DummyBuilder:
        def __init__(self):
            self.models = {}

        def register_model(self, name, config):
            self.models[name] = config

    visitor.builder = DummyBuilder()

    class FakeNumber:
        def INT(self):
            return SimpleNamespace(getText=lambda: "5")

        def FLOAT(self):
            return None

        def getText(self):
            return "5"

    class FakeExp:
        def prefixexp(self):
            return None

        def string(self):
            return None

        def number(self):
            return FakeNumber()

        def NIL(self):
            return None

        def FALSE(self):
            return None

        def TRUE(self):
            return None

        def tableconstructor(self):
            return None

        def getText(self):
            return "5"

    class FakeExplist:
        def exp(self):
            return [FakeExp()]

    class FakeArgs:
        def explist(self):
            return FakeExplist()

        def tableconstructor(self):
            return None

    class FakeChild:
        symbol = object()

        def getText(self):
            return "Model"

        def accept(self, _visitor):
            return None

    class FakeCtx:
        start = None

        def getChildCount(self):
            return 1

        def getChild(self, _index):
            return FakeChild()

        def varOrExp(self):
            return None

        def args(self):
            return [FakeArgs()]

        def getText(self):
            return "Model(5)"

    visitor.visitFunctioncall(FakeCtx())
    assert visitor.builder.models == {}


def test_visit_functioncall_tool_curried_adds_error():
    visitor = TactusDSLVisitor()
    visitor.builder = SimpleNamespace()

    class FakeString:
        def NORMALSTRING(self):
            return SimpleNamespace(getText=lambda: '"bad_tool"')

        def CHARSTRING(self):
            return None

    class FakeExp:
        def prefixexp(self):
            return None

        def string(self):
            return FakeString()

        def number(self):
            return None

        def NIL(self):
            return None

        def FALSE(self):
            return None

        def TRUE(self):
            return None

        def tableconstructor(self):
            return None

        def getText(self):
            return '"bad_tool"'

    class FakeExplist:
        def exp(self):
            return [FakeExp()]

    class FakeArgs:
        def explist(self):
            return FakeExplist()

        def tableconstructor(self):
            return None

    class FakeChild:
        symbol = object()

        def getText(self):
            return "Tool"

        def accept(self, _visitor):
            return None

    class FakeCtx:
        start = None

        def getChildCount(self):
            return 1

        def getChild(self, _index):
            return FakeChild()

        def varOrExp(self):
            return None

        def args(self):
            return [FakeArgs()]

        def getText(self):
            return 'Tool("bad_tool")'

    visitor.visitFunctioncall(FakeCtx())
    assert visitor.errors
    assert "Curried Tool syntax is not supported" in visitor.errors[-1].message


def test_visit_functioncall_tool_non_string_args_skips_error():
    visitor = TactusDSLVisitor()
    visitor.builder = SimpleNamespace()

    class FakeNumber:
        def INT(self):
            return SimpleNamespace(getText=lambda: "4")

        def FLOAT(self):
            return None

        def getText(self):
            return "4"

    class FakeExp:
        def prefixexp(self):
            return None

        def string(self):
            return None

        def number(self):
            return FakeNumber()

        def NIL(self):
            return None

        def FALSE(self):
            return None

        def TRUE(self):
            return None

        def tableconstructor(self):
            return None

        def getText(self):
            return "4"

    class FakeExplist:
        def exp(self):
            return [FakeExp()]

    class FakeArgs:
        def explist(self):
            return FakeExplist()

        def tableconstructor(self):
            return None

    class FakeChild:
        symbol = object()

        def getText(self):
            return "Tool"

        def accept(self, _visitor):
            return None

    class FakeCtx:
        start = None

        def getChildCount(self):
            return 1

        def getChild(self, _index):
            return FakeChild()

        def varOrExp(self):
            return None

        def args(self):
            return [FakeArgs()]

        def getText(self):
            return "Tool(4)"

    visitor.visitFunctioncall(FakeCtx())
    assert visitor.errors == []


def test_visit_functioncall_toolset_registers_toolset():
    visitor = TactusDSLVisitor()

    class DummyBuilder:
        def __init__(self):
            self.toolsets = {}

        def register_toolset(self, name, config):
            self.toolsets[name] = config

    visitor.builder = DummyBuilder()

    class FakeString:
        def NORMALSTRING(self):
            return SimpleNamespace(getText=lambda: '"tools"')

        def CHARSTRING(self):
            return None

    class FakeNumber:
        def INT(self):
            return SimpleNamespace(getText=lambda: "3")

        def FLOAT(self):
            return None

        def getText(self):
            return "3"

    class FakeField:
        def NAME(self):
            return SimpleNamespace(getText=lambda: "timeout")

        def exp(self, _index=None):
            return [FakeValueExp()] if _index is None else FakeValueExp()

    class FakeFieldList:
        def field(self):
            return [FakeField()]

    class FakeTable:
        def fieldlist(self):
            return FakeFieldList()

    class FakeStringExp:
        def prefixexp(self):
            return None

        def string(self):
            return FakeString()

        def number(self):
            return None

        def NIL(self):
            return None

        def FALSE(self):
            return None

        def TRUE(self):
            return None

        def tableconstructor(self):
            return None

        def getText(self):
            return '"tools"'

    class FakeValueExp:
        def prefixexp(self):
            return None

        def string(self):
            return None

        def number(self):
            return FakeNumber()

        def NIL(self):
            return None

        def FALSE(self):
            return None

        def TRUE(self):
            return None

        def tableconstructor(self):
            return None

        def getText(self):
            return "3"

    class FakeTableExp:
        def prefixexp(self):
            return None

        def string(self):
            return None

        def number(self):
            return None

        def NIL(self):
            return None

        def FALSE(self):
            return None

        def TRUE(self):
            return None

        def tableconstructor(self):
            return FakeTable()

        def getText(self):
            return "{}"

    class FakeExplist:
        def exp(self):
            return [FakeStringExp(), FakeTableExp()]

    class FakeArgs:
        def explist(self):
            return FakeExplist()

        def tableconstructor(self):
            return None

    class FakeChild:
        symbol = object()

        def getText(self):
            return "Toolset"

        def accept(self, _visitor):
            return None

    class FakeCtx:
        start = None

        def getChildCount(self):
            return 1

        def getChild(self, _index):
            return FakeChild()

        def varOrExp(self):
            return None

        def args(self):
            return [FakeArgs()]

        def getText(self):
            return 'Toolset("tools", {timeout = 3})'

    visitor.visitFunctioncall(FakeCtx())
    assert visitor.builder.toolsets["tools"]["timeout"] == 3


def test_extract_arguments_no_children_skips_method_chain():
    visitor = TactusDSLVisitor()

    class FakeString:
        def NORMALSTRING(self):
            return SimpleNamespace(getText=lambda: '"first"')

        def CHARSTRING(self):
            return None

    class FakeExp:
        def prefixexp(self):
            return None

        def string(self):
            return FakeString()

        def number(self):
            return None

        def NIL(self):
            return None

        def FALSE(self):
            return None

        def TRUE(self):
            return None

        def tableconstructor(self):
            return None

        def getText(self):
            return '"first"'

    class FakeExplist:
        def exp(self):
            return [FakeExp()]

    class FakeArgs:
        def explist(self):
            return FakeExplist()

        def tableconstructor(self):
            return None

    class FakeCtx:
        def getChildCount(self):
            return 0

        def getChild(self, _index):
            return None

        def args(self):
            return [FakeArgs(), FakeArgs()]

    assert visitor._extract_arguments(FakeCtx()) == ["first", "first"]


def test_parse_expression_field_builder_without_table_options():  # noqa: F811
    visitor = TactusDSLVisitor()

    class FakeArgs:
        def tableconstructor(self):
            return None

    class FakeFuncCall:
        def NAME(self):
            return [
                SimpleNamespace(getText=lambda: "field"),
                SimpleNamespace(getText=lambda: "string"),
            ]

        def args(self, _index=None):
            return [FakeArgs()] if _index is None else FakeArgs()

    class FakePrefix:
        def functioncall(self):
            return FakeFuncCall()

    class FakeExp:
        def prefixexp(self):
            return FakePrefix()

        def number(self):
            return None

        def string(self):
            return None

        def NIL(self):
            return None

        def FALSE(self):
            return None

        def TRUE(self):
            return None

        def tableconstructor(self):
            return None

    result = visitor._parse_expression(FakeExp())
    assert result == {"type": "string", "required": False}


def test_parse_expression_field_builder_without_args_returns_defaults():
    visitor = TactusDSLVisitor()

    class FakeFuncCall:
        def NAME(self):
            return [
                SimpleNamespace(getText=lambda: "field"),
                SimpleNamespace(getText=lambda: "string"),
            ]

        def args(self, _index=None):
            return []

    class FakePrefix:
        def functioncall(self):
            return FakeFuncCall()

    class FakeExp:
        def prefixexp(self):
            return FakePrefix()

        def number(self):
            return None

        def string(self):
            return None

        def NIL(self):
            return None

        def FALSE(self):
            return None

        def TRUE(self):
            return None

        def tableconstructor(self):
            return None

    result = visitor._parse_expression(FakeExp())
    assert result == {"type": "string", "required": False}


def test_parse_table_constructor_array_element():  # noqa: F811
    visitor = TactusDSLVisitor()

    class FakeExp:
        def prefixexp(self):
            return None

        def number(self):
            class FakeNumber:
                def INT(self):
                    return SimpleNamespace(getText=lambda: "3")

                def FLOAT(self):
                    return None

                def getText(self):
                    return "3"

            return FakeNumber()

        def string(self):
            return None

        def NIL(self):
            return None

        def FALSE(self):
            return None

        def TRUE(self):
            return None

        def tableconstructor(self):
            return None

        def getText(self):
            return "3"

    class FakeField:
        def NAME(self):
            return None

        def exp(self, _index=None):
            return FakeExp() if _index is not None else [FakeExp()]

    class FakeFieldList:
        def field(self):
            return [FakeField()]

    class FakeTable:
        def fieldlist(self):
            return FakeFieldList()

    assert visitor._parse_table_constructor(FakeTable()) == [3]


def test_parse_table_constructor_empty_exp_field_returns_empty_list():
    visitor = TactusDSLVisitor()

    class FakeField:
        def NAME(self):
            return None

        def exp(self, _index=None):
            return []

    class FakeFieldList:
        def field(self):
            return [FakeField()]

    class FakeTable:
        def fieldlist(self):
            return FakeFieldList()

    assert visitor._parse_table_constructor(FakeTable()) == []
