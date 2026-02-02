from types import SimpleNamespace

from tactus.validation.semantic_visitor import TactusDSLVisitor


def test_parse_functioncall_expression_variants(monkeypatch):
    visitor = TactusDSLVisitor()

    monkeypatch.setattr(visitor, "_extract_function_name", lambda _ctx: "template")
    monkeypatch.setattr(visitor, "_extract_arguments", lambda _ctx: ["Hi", {"name": "Ada"}])
    assert visitor._parse_functioncall_expression(SimpleNamespace()) == {
        "template": "Hi",
        "vars": {"name": "Ada"},
    }

    monkeypatch.setattr(visitor, "_extract_function_name", lambda _ctx: "system")
    monkeypatch.setattr(visitor, "_extract_arguments", lambda _ctx: ["hi"])
    assert visitor._parse_functioncall_expression(SimpleNamespace()) == {
        "type": "system",
        "content": "hi",
    }

    monkeypatch.setattr(visitor, "_extract_function_name", lambda _ctx: "system")
    monkeypatch.setattr(
        visitor, "_extract_arguments", lambda _ctx: [{"template": "x", "vars": {"a": 1}}]
    )
    assert visitor._parse_functioncall_expression(SimpleNamespace()) == {
        "type": "system",
        "template": "x",
        "vars": {"a": 1},
    }

    monkeypatch.setattr(visitor, "_extract_function_name", lambda _ctx: "user")
    monkeypatch.setattr(visitor, "_extract_arguments", lambda _ctx: [123])
    assert visitor._parse_functioncall_expression(SimpleNamespace()) == {
        "type": "user",
        "content": "123",
    }

    monkeypatch.setattr(visitor, "_extract_function_name", lambda _ctx: "context")
    monkeypatch.setattr(visitor, "_extract_arguments", lambda _ctx: ["pack", {"max_tokens": 10}])
    assert visitor._parse_functioncall_expression(SimpleNamespace()) == {
        "type": "context",
        "name": "pack",
        "budget": {"max_tokens": 10},
    }

    monkeypatch.setattr(visitor, "_extract_function_name", lambda _ctx: "context")
    monkeypatch.setattr(visitor, "_extract_arguments", lambda _ctx: ["pack", "bad"])
    assert visitor._parse_functioncall_expression(SimpleNamespace()) == {
        "type": "context",
        "name": "pack",
    }

    monkeypatch.setattr(visitor, "_extract_function_name", lambda _ctx: "history")
    monkeypatch.setattr(visitor, "_extract_arguments", lambda _ctx: [])
    assert visitor._parse_functioncall_expression(SimpleNamespace()) == {"type": "history"}


def test_parse_functioncall_expression_skips_bad_template(monkeypatch):
    visitor = TactusDSLVisitor()
    monkeypatch.setattr(visitor, "_extract_function_name", lambda _ctx: "template")
    monkeypatch.setattr(visitor, "_extract_arguments", lambda _ctx: [123, "bad"])
    assert visitor._parse_functioncall_expression(SimpleNamespace()) is None

    monkeypatch.setattr(visitor, "_extract_function_name", lambda _ctx: "template")
    monkeypatch.setattr(visitor, "_extract_arguments", lambda _ctx: ["hi", "bad"])
    assert visitor._parse_functioncall_expression(SimpleNamespace()) == {
        "template": "hi",
        "vars": {},
    }

    monkeypatch.setattr(visitor, "_extract_function_name", lambda _ctx: "system")
    monkeypatch.setattr(visitor, "_extract_arguments", lambda _ctx: [])
    assert visitor._parse_functioncall_expression(SimpleNamespace()) is None

    monkeypatch.setattr(visitor, "_extract_function_name", lambda _ctx: "context")
    monkeypatch.setattr(visitor, "_extract_arguments", lambda _ctx: [])
    assert visitor._parse_functioncall_expression(SimpleNamespace()) is None

    monkeypatch.setattr(visitor, "_extract_function_name", lambda _ctx: "context")
    monkeypatch.setattr(visitor, "_extract_arguments", lambda _ctx: ["pack", {"max_tokens": 1}])
    assert visitor._parse_functioncall_expression(SimpleNamespace()) == {
        "type": "context",
        "name": "pack",
        "budget": {"max_tokens": 1},
    }

    monkeypatch.setattr(visitor, "_extract_function_name", lambda _ctx: None)
    monkeypatch.setattr(visitor, "_extract_arguments", lambda _ctx: [])
    assert visitor._parse_functioncall_expression(SimpleNamespace()) is None

    monkeypatch.setattr(visitor, "_extract_function_name", lambda _ctx: "unknown")
    monkeypatch.setattr(visitor, "_extract_arguments", lambda _ctx: [])
    assert visitor._parse_functioncall_expression(SimpleNamespace()) is None


def test_direct_corpus_and_retriever_declarations_error(monkeypatch):
    visitor = TactusDSLVisitor()

    class FakeFunctionCall:
        def getText(self):
            return "Corpus { }"

    class FakePrefixExp:
        def functioncall(self):
            return FakeFunctionCall()

    class FakeExpression:
        def prefixexp(self):
            return FakePrefixExp()

    monkeypatch.setattr(visitor, "_extract_function_name", lambda _ctx: "Corpus")
    visitor._check_assignment_based_declaration("support", FakeExpression())
    assert visitor.errors


def test_direct_corpus_declaration_with_dotted_name_allowed(monkeypatch):
    visitor = TactusDSLVisitor()

    class FakeFunctionCall:
        def getText(self):
            return "vector.Corpus { }"

        def args(self):
            return None

    class FakePrefixExp:
        def functioncall(self):
            return FakeFunctionCall()

    class FakeExpression:
        def prefixexp(self):
            return FakePrefixExp()

    monkeypatch.setattr(visitor, "_extract_function_name", lambda _ctx: "Corpus")
    visitor._check_assignment_based_declaration("support", FakeExpression())
    assert visitor.errors == []


def test_assignment_based_compactor_registers(monkeypatch):
    visitor = TactusDSLVisitor()

    class FakeFunctionCall:
        def getText(self):
            return "Compactor { }"

    class FakePrefixExp:
        def functioncall(self):
            return FakeFunctionCall()

    class FakeExpression:
        def prefixexp(self):
            return FakePrefixExp()

    monkeypatch.setattr(visitor, "_extract_function_name", lambda _ctx: "Compactor")
    monkeypatch.setattr(visitor, "_extract_single_table_arg", lambda _ctx: {})
    visitor._check_assignment_based_declaration("compress", FakeExpression())
    assert "compress" in visitor.builder.registry.compactors


def test_parse_expression_functioncall_branch(monkeypatch):
    visitor = TactusDSLVisitor()

    class FakePrefixExp:
        def functioncall(self):
            return None

    class FakeExpression:
        def prefixexp(self):
            return FakePrefixExp()

    class FakeCtx:
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

        def functioncall(self):
            return SimpleNamespace()

    monkeypatch.setattr(visitor, "_parse_functioncall_expression", lambda _ctx: {"type": "history"})
    assert visitor._parse_expression(FakeCtx()) == {"type": "history"}

    visitor.errors = []
    monkeypatch.setattr(visitor, "_extract_function_name", lambda _ctx: "Retriever")
    visitor._check_assignment_based_declaration("support", FakeExpression())
    assert visitor.errors == []
