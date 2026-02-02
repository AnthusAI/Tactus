from biblicus.context import ContextPack, ContextPackBlock
from tactus.core.context_assembler import ContextAssembler
from tactus.core.context_models import ContextDeclaration


def test_context_assembler_raises_for_missing_context():
    assembler = ContextAssembler({})
    try:
        assembler.assemble(
            context_name="missing",
            base_system_prompt="",
            history_messages=[],
            user_message="",
            template_context={},
        )
    except ValueError as exc:
        assert "Context 'missing'" in str(exc)
    else:
        raise AssertionError("Expected ValueError for missing context")


def test_context_assembler_explicit_messages_with_history():
    context_spec = ContextDeclaration(
        name="support",
        messages=[
            {"type": "system", "content": "You are a support agent."},
            {"type": "history"},
            {"type": "user", "template": "Question: {input.question}", "vars": {}},
        ],
    )
    assembler = ContextAssembler({"support": context_spec})
    result = assembler.assemble(
        context_name="support",
        base_system_prompt="ignored",
        history_messages=[{"role": "assistant", "content": "Hello"}],
        user_message="fallback",
        template_context={"input": {"question": "Where is my order?"}, "context": {}},
    )

    assert result.system_prompt == "You are a support agent."
    assert result.user_message == "Question: Where is my order?"
    assert result.history == [{"role": "assistant", "content": "Hello"}]


def test_context_assembler_retriever_pack(monkeypatch):
    from tactus.core.context_models import ContextDeclaration as Decl

    context_spec = Decl(
        name="support",
        messages=[
            {"type": "system", "content": "Use this context."},
            {"type": "context", "name": "wikitext_search"},
            {"type": "user", "content": "Question"},
        ],
    )
    retriever_spec = type(
        "RetrieverSpec",
        (),
        {
            "config": {
                "query": "Valkyria Chronicles III",
                "limit": 1,
                "maximum_total_characters": 80,
            }
        },
    )()

    def fake_retrieve(request):
        text = "Valkyria Chronicles III"
        return ContextPack(
            text=text,
            evidence_count=1,
            blocks=[ContextPackBlock(evidence_item_id="fake-1", text=text, metadata=None)],
        )

    monkeypatch.setattr("tactus.core.retrieval.retrieve_wikitext2", fake_retrieve)

    assembler = ContextAssembler(
        {"support": context_spec}, retriever_registry={"wikitext_search": retriever_spec}
    )
    result = assembler.assemble(
        context_name="support",
        base_system_prompt="",
        history_messages=[],
        user_message="",
        template_context={"input": {}, "context": {}},
        retriever_override=fake_retrieve,
    )

    assert "Valkyria Chronicles III" in result.system_prompt


def test_context_assembler_interpolates_context_pack_in_template():
    context_spec = ContextDeclaration(
        name="support",
        messages=[
            {"type": "context", "name": "wikitext_search"},
            {
                "type": "system",
                "template": "Use this:\n{context.wikitext_search}",
                "vars": {},
            },
            {"type": "user", "content": "Question"},
        ],
    )
    retriever_spec = type("RetrieverSpec", (), {"config": {}})()

    def fake_retrieve(request):
        text = "Context snippet"
        return ContextPack(
            text=text,
            evidence_count=1,
            blocks=[ContextPackBlock(evidence_item_id="fake-1", text=text, metadata=None)],
        )

    assembler = ContextAssembler(
        {"support": context_spec}, retriever_registry={"wikitext_search": retriever_spec}
    )
    result = assembler.assemble(
        context_name="support",
        base_system_prompt="",
        history_messages=[],
        user_message="",
        template_context={"input": {}, "context": {}},
        retriever_override=fake_retrieve,
    )

    assert "Context snippet" in result.system_prompt
    assert "Use this:\nContext snippet" in result.system_prompt


def test_context_assembler_nested_default_context_pack():
    nested_context = ContextDeclaration(
        name="nested",
        policy={"input_budget": {"max_tokens": 20}},
        packs=[{"name": "wikitext_search"}],
    )
    parent_context = ContextDeclaration(
        name="support",
        packs=[{"name": "nested"}],
    )
    retriever_spec = type("RetrieverSpec", (), {"config": {}})()

    def fake_retrieve(request):
        text = "Nested snippet"
        return ContextPack(
            text=text,
            evidence_count=1,
            blocks=[ContextPackBlock(evidence_item_id="fake-1", text=text, metadata=None)],
        )

    assembler = ContextAssembler(
        {"support": parent_context, "nested": nested_context},
        retriever_registry={"wikitext_search": retriever_spec},
    )
    result = assembler.assemble(
        context_name="support",
        base_system_prompt="Base prompt",
        history_messages=[],
        user_message="",
        template_context={"input": {}, "context": {}},
        retriever_override=fake_retrieve,
    )

    assert "Base prompt" in result.system_prompt
    assert "Nested snippet" in result.system_prompt


def test_context_assembler_nested_context_pack_with_context():
    nested_context = ContextDeclaration(
        name="nested",
        messages=[
            {"type": "system", "content": "Nested context"},
            {"type": "context", "name": "wikitext_search"},
        ],
    )
    parent_context = ContextDeclaration(
        name="support",
        messages=[
            {"type": "context", "name": "nested"},
            {"type": "user", "content": "Question"},
        ],
    )
    retriever_spec = type("RetrieverSpec", (), {"config": {}})()

    def fake_retrieve(request):
        text = "Nested snippet"
        return ContextPack(
            text=text,
            evidence_count=1,
            blocks=[ContextPackBlock(evidence_item_id="fake-1", text=text, metadata=None)],
        )

    assembler = ContextAssembler(
        {"support": parent_context, "nested": nested_context},
        retriever_registry={"wikitext_search": retriever_spec},
    )
    result = assembler.assemble(
        context_name="support",
        base_system_prompt="",
        history_messages=[],
        user_message="",
        template_context={"input": {}, "context": {}},
        retriever_override=fake_retrieve,
    )

    assert "Nested context" in result.system_prompt
    assert "Nested snippet" in result.system_prompt


def test_context_assembler_nested_pack_budget_caps_retriever():
    nested_context = ContextDeclaration(
        name="nested",
        messages=[
            {"type": "system", "content": "Nested context"},
            {"type": "context", "name": "wikitext_search"},
        ],
        policy={
            "input_budget": {"max_tokens": 50},
            "pack_budget": {"default_ratio": 1.0},
        },
    )
    parent_context = ContextDeclaration(
        name="support",
        messages=[
            {"type": "context", "name": "nested", "budget": {"max_tokens": 3}},
            {"type": "user", "content": "Question"},
        ],
    )
    retriever_spec = type("RetrieverSpec", (), {"config": {}})()
    calls = []

    def fake_retrieve(request):
        calls.append(request.maximum_total_characters)
        text = "Nested snippet"
        return ContextPack(
            text=text,
            evidence_count=1,
            blocks=[ContextPackBlock(evidence_item_id="fake-1", text=text, metadata=None)],
        )

    assembler = ContextAssembler(
        {"support": parent_context, "nested": nested_context},
        retriever_registry={"wikitext_search": retriever_spec},
    )
    assembler.assemble(
        context_name="support",
        base_system_prompt="",
        history_messages=[],
        user_message="",
        template_context={"input": {}, "context": {}},
        retriever_override=fake_retrieve,
    )

    assert len(calls) == 1
    assert calls[0] <= 12


def test_context_assembler_nested_pack_regenerates_under_budget():
    nested_context = ContextDeclaration(
        name="nested",
        policy={
            "input_budget": {"max_tokens": 50},
            "pack_budget": {"default_ratio": 1.0},
            "overflow": "compact",
            "max_iterations": 3,
        },
        messages=[
            {"type": "system", "content": "Nested context"},
            {"type": "context", "name": "wikitext_search"},
        ],
    )
    parent_context = ContextDeclaration(
        name="support",
        policy={"input_budget": {"max_tokens": 5}, "overflow": "compact", "max_iterations": 3},
        messages=[
            {"type": "context", "name": "nested", "budget": {"max_tokens": 4}},
            {"type": "user", "content": "Question"},
        ],
    )
    retriever_spec = type("RetrieverSpec", (), {"config": {}})()
    calls = []

    def fake_retrieve(request):
        calls.append(request.maximum_total_characters)
        text = "Nested snippet long " * 10
        return ContextPack(
            text=text,
            evidence_count=1,
            blocks=[ContextPackBlock(evidence_item_id="fake-1", text=text, metadata=None)],
        )

    assembler = ContextAssembler(
        {"support": parent_context, "nested": nested_context},
        retriever_registry={"wikitext_search": retriever_spec},
    )
    assembler.assemble(
        context_name="support",
        base_system_prompt="",
        history_messages=[],
        user_message="",
        template_context={"input": {}, "context": {}},
        retriever_override=fake_retrieve,
    )

    assert len(calls) >= 2
    assert calls[-1] < calls[0]


def test_context_assembler_explicit_pack_regenerates_under_budget():
    context_spec = ContextDeclaration(
        name="support",
        policy={
            "input_budget": {"max_tokens": 10},
            "pack_budget": {"default_ratio": 1.0},
            "overflow": "compact",
            "max_iterations": 3,
        },
        messages=[
            {"type": "context", "name": "search_primary"},
            {"type": "context", "name": "search_secondary"},
            {"type": "user", "content": "Question"},
        ],
    )
    retriever_spec = type("RetrieverSpec", (), {"config": {}})()
    calls = []

    def fake_retrieve(request):
        calls.append(request.maximum_total_characters)
        text = "Valkyria Chronicles III long excerpt " * 5
        return ContextPack(
            text=text,
            evidence_count=1,
            blocks=[ContextPackBlock(evidence_item_id="fake-1", text=text, metadata=None)],
        )

    assembler = ContextAssembler(
        {"support": context_spec},
        retriever_registry={
            "search_primary": retriever_spec,
            "search_secondary": retriever_spec,
        },
    )
    assembler.assemble(
        context_name="support",
        base_system_prompt="",
        history_messages=[],
        user_message="",
        template_context={"input": {}, "context": {}},
        retriever_override=fake_retrieve,
    )

    assert len(calls) >= 4
    assert calls[2] < calls[0]
    assert calls[3] < calls[1]


def test_context_assembler_explicit_pack_priority_allocation():
    context_spec = ContextDeclaration(
        name="support",
        policy={
            "input_budget": {"max_tokens": 10},
            "pack_budget": {"default_ratio": 1.0},
            "overflow": "compact",
            "max_iterations": 2,
        },
        messages=[
            {"type": "context", "name": "search_primary", "priority": 2},
            {"type": "context", "name": "search_secondary", "priority": 1},
            {"type": "context", "name": "search_tertiary", "priority": 0},
            {"type": "user", "content": "Question"},
        ],
    )
    retriever_spec = type("RetrieverSpec", (), {"config": {}})()
    calls = []

    def fake_retrieve(request):
        calls.append(request.maximum_total_characters)
        text = "Valkyria Chronicles III long excerpt " * 5
        return ContextPack(
            text=text,
            evidence_count=1,
            blocks=[ContextPackBlock(evidence_item_id="fake-1", text=text, metadata=None)],
        )

    assembler = ContextAssembler(
        {"support": context_spec},
        retriever_registry={
            "search_primary": retriever_spec,
            "search_secondary": retriever_spec,
            "search_tertiary": retriever_spec,
        },
    )
    assembler.assemble(
        context_name="support",
        base_system_prompt="",
        history_messages=[],
        user_message="",
        template_context={"input": {}, "context": {}},
        retriever_override=fake_retrieve,
    )

    assert len(calls) >= 3
    assert calls[0] >= calls[1]
    assert calls[1] >= calls[2]


def test_context_assembler_explicit_pack_weight_allocation():
    context_spec = ContextDeclaration(
        name="support",
        policy={
            "input_budget": {"max_tokens": 9},
            "pack_budget": {"default_ratio": 1.0},
            "overflow": "compact",
            "max_iterations": 2,
        },
        messages=[
            {"type": "context", "name": "search_primary", "weight": 2.0},
            {"type": "context", "name": "search_secondary", "weight": 1.0},
            {"type": "user", "content": "Question"},
        ],
    )
    retriever_spec = type("RetrieverSpec", (), {"config": {}})()
    calls = []

    def fake_retrieve(request):
        calls.append(request.maximum_total_characters)
        text = "Valkyria Chronicles III long excerpt " * 5
        return ContextPack(
            text=text,
            evidence_count=1,
            blocks=[ContextPackBlock(evidence_item_id="fake-1", text=text, metadata=None)],
        )

    assembler = ContextAssembler(
        {"support": context_spec},
        retriever_registry={
            "search_primary": retriever_spec,
            "search_secondary": retriever_spec,
        },
    )
    assembler.assemble(
        context_name="support",
        base_system_prompt="",
        history_messages=[],
        user_message="",
        template_context={"input": {}, "context": {}},
        retriever_override=fake_retrieve,
    )

    assert len(calls) >= 2
    assert calls[0] > calls[1]


def test_context_assembler_unknown_pack_raises():
    context_spec = ContextDeclaration(
        name="support",
        messages=[{"type": "context", "name": "unknown"}, {"type": "user", "content": "Q"}],
    )
    assembler = ContextAssembler({"support": context_spec})
    try:
        assembler.assemble(
            context_name="support",
            base_system_prompt="",
            history_messages=[],
            user_message="",
            template_context={"input": {}, "context": {}},
        )
    except NotImplementedError as exc:
        assert "unknown" in str(exc)
    else:
        raise AssertionError("Expected NotImplementedError for unknown pack")


def test_context_assembler_missing_compactor_raises():
    context_spec = ContextDeclaration(
        name="support",
        policy={"input_budget": {"max_tokens": 1}, "overflow": "compact", "compactor": "nope"},
        messages=[{"type": "system", "content": "one two"}],
    )
    assembler = ContextAssembler({"support": context_spec})
    try:
        assembler.assemble(
            context_name="support",
            base_system_prompt="",
            history_messages=[],
            user_message="",
            template_context={"input": {}, "context": {}},
        )
    except ValueError as exc:
        assert "Compactor 'nope'" in str(exc)
    else:
        raise AssertionError("Expected ValueError for missing compactor")


def test_context_assembler_overflow_not_compact_returns_untrimmed():
    context_spec = ContextDeclaration(
        name="support",
        policy={"input_budget": {"max_tokens": 2}, "overflow": "truncate"},
        messages=[{"type": "system", "content": "one two three"}],
    )
    assembler = ContextAssembler({"support": context_spec})
    result = assembler.assemble(
        context_name="support",
        base_system_prompt="",
        history_messages=[],
        user_message="",
        template_context={"input": {}, "context": {}},
    )
    assert result.system_prompt == "one two three"


def test_context_assembler_allocate_pack_budget_ratio_without_input_budget():
    context_spec = ContextDeclaration(name="support")
    assembler = ContextAssembler({"support": context_spec})
    pack_budget = {"ratio": 0.5}
    assert assembler._allocate_pack_budget(pack_budget, policy=None, weight=None) is None


def test_context_assembler_explicit_messages_without_history():
    context_spec = ContextDeclaration(
        name="support",
        messages=[
            {"type": "system", "content": "System rules."},
            {"type": "user", "content": "User question"},
        ],
    )
    assembler = ContextAssembler({"support": context_spec})
    result = assembler.assemble(
        context_name="support",
        base_system_prompt="ignored",
        history_messages=[{"role": "assistant", "content": "Hello"}],
        user_message="fallback",
        template_context={},
    )

    assert result.system_prompt == "System rules."
    assert result.user_message == "User question"
    assert result.history == []


def test_context_assembler_default_plan_uses_base_prompt():
    context_spec = ContextDeclaration(name="support")
    assembler = ContextAssembler({"support": context_spec})
    result = assembler.assemble(
        context_name="support",
        base_system_prompt="Base prompt",
        history_messages=[{"role": "assistant", "content": "Hello"}],
        user_message="Hi",
        template_context={},
    )

    assert result.system_prompt == "Base prompt"
    assert result.user_message == "Hi"
    assert result.history == [{"role": "assistant", "content": "Hello"}]


def test_context_assembler_default_pack_priority_allocation():
    context_spec = ContextDeclaration(
        name="support",
        policy={
            "input_budget": {"max_tokens": 10},
            "pack_budget": {"default_ratio": 1.0},
        },
        packs=[
            {"name": "primary", "priority": 2},
            {"name": "secondary", "priority": 1},
            {"name": "tertiary", "priority": 0},
        ],
    )
    retriever_spec = type("RetrieverSpec", (), {"config": {}})()
    retriever_registry = {
        "primary": retriever_spec,
        "secondary": retriever_spec,
        "tertiary": retriever_spec,
    }
    calls = []

    def fake_retrieve(request):
        calls.append(request.maximum_total_characters)
        text = "context"
        return ContextPack(
            text=text,
            evidence_count=1,
            blocks=[ContextPackBlock(evidence_item_id="fake-1", text=text, metadata=None)],
        )

    assembler = ContextAssembler({"support": context_spec}, retriever_registry=retriever_registry)
    assembler.assemble(
        context_name="support",
        base_system_prompt="",
        history_messages=[],
        user_message="",
        template_context={"input": {}, "context": {}},
        retriever_override=fake_retrieve,
    )

    assert len(calls) == 3
    assert calls[0] > calls[1]
    assert calls[1] >= calls[2]


def test_context_assembler_uses_named_compactor():
    context_spec = ContextDeclaration(
        name="support",
        policy={
            "input_budget": {"max_tokens": 3},
            "overflow": "compact",
            "compactor": "tiny",
        },
        messages=[{"type": "system", "content": "one two three four five"}],
    )
    compactor_spec = type("CompactorSpec", (), {"config": {"type": "truncate"}})()
    assembler = ContextAssembler(
        {"support": context_spec}, compactor_registry={"tiny": compactor_spec}
    )
    result = assembler.assemble(
        context_name="support",
        base_system_prompt="",
        history_messages=[],
        user_message="",
        template_context={"input": {}, "context": {}},
    )

    assert result.system_prompt == "one two three"
    assert result.token_count == 3


def test_context_assembler_trims_history_when_over_budget():
    context_spec = ContextDeclaration(
        name="support",
        policy={
            "input_budget": {"max_tokens": 5},
            "overflow": "compact",
        },
        messages=[
            {"type": "system", "content": "System prompt"},
            {"type": "history"},
            {"type": "user", "content": "User message"},
        ],
    )
    assembler = ContextAssembler({"support": context_spec})
    history = [
        {"role": "assistant", "content": "one two"},
        {"role": "assistant", "content": "three four"},
    ]
    result = assembler.assemble(
        context_name="support",
        base_system_prompt="",
        history_messages=history,
        user_message="",
        template_context={"input": {}, "context": {}},
    )

    assert result.token_count <= 5
    assert len(result.history) < len(history)


def test_context_assembler_compacts_nested_pack_budget():
    nested = ContextDeclaration(
        name="nested_pack",
        messages=[{"type": "system", "content": "one two three four five"}],
    )
    parent = ContextDeclaration(
        name="support",
        policy={"overflow": "compact"},
        messages=[
            {"type": "system", "content": "Use this."},
            {"type": "context", "name": "nested_pack", "budget": {"max_tokens": 3}},
            {"type": "user", "content": "Question"},
        ],
    )
    assembler = ContextAssembler({"support": parent, "nested_pack": nested})
    result = assembler.assemble(
        context_name="support",
        base_system_prompt="",
        history_messages=[],
        user_message="",
        template_context={"input": {}, "context": {}},
    )

    assert "one two three" in result.system_prompt
    assert "four" not in result.system_prompt
