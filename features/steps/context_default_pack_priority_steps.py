from behave import given, when, then

from biblicus.context import ContextPack, ContextPackBlock
from tactus.core.context_assembler import ContextAssembler
from tactus.core.registry import RegistryBuilder


@given("a default Context with prioritized packs and a shared budget")
def step_default_context_prioritized_packs(context):
    builder = RegistryBuilder()
    builder.register_corpus(
        "wikitext",
        {"split": "train", "maximum_cache_total_items": 2000},
    )
    builder.register_retriever(
        "search_primary",
        {
            "corpus": "wikitext",
            "retriever_id": "wikitext2",
            "query": "Valkyria Chronicles III",
            "limit": 5,
            "maximum_total_characters": 800,
        },
    )
    builder.register_retriever(
        "search_secondary",
        {
            "corpus": "wikitext",
            "retriever_id": "wikitext2",
            "query": "Valkyria Chronicles III",
            "limit": 5,
            "maximum_total_characters": 800,
        },
    )
    builder.register_retriever(
        "search_tertiary",
        {
            "corpus": "wikitext",
            "retriever_id": "wikitext2",
            "query": "Valkyria Chronicles III",
            "limit": 5,
            "maximum_total_characters": 800,
        },
    )
    builder.register_context(
        "support_context",
        {
            "policy": {
                "input_budget": {"max_tokens": 10},
                "pack_budget": {"default_ratio": 1.0},
            },
            "packs": [
                {"name": "search_primary", "priority": 2},
                {"name": "search_secondary", "priority": 1},
                {"name": "search_tertiary", "priority": 0},
            ],
        },
    )
    context.registry = builder.registry
    context.context_name = "support_context"
    context.calls = []


@when("I assemble that default Context with shared pack budgets")
def step_assemble_default_context_with_shared_budget(context):
    def fake_retrieve(request):
        context.calls.append(request.maximum_total_characters)
        text = "Valkyria Chronicles III"
        return ContextPack(
            text=text,
            evidence_count=1,
            blocks=[ContextPackBlock(evidence_item_id="fake-1", text=text, metadata=None)],
        )

    assembler = ContextAssembler(
        context.registry.contexts,
        retriever_registry=context.registry.retrievers,
        corpus_registry=context.registry.corpora,
    )
    assembler.assemble(
        context_name=context.context_name,
        base_system_prompt="",
        history_messages=[],
        user_message="",
        template_context={"input": {}, "context": {}},
        retriever_override=fake_retrieve,
    )


@then("higher-priority packs should receive greater or equal budgets")
def step_priority_budgets(context):
    assert len(context.calls) == 3
    assert context.calls[0] > context.calls[1]
    assert context.calls[1] >= context.calls[2]


@then("total pack budget should not exceed the shared limit")
def step_total_budget_limit(context):
    total_chars = sum(context.calls)
    shared_budget_tokens = 10
    assert total_chars <= shared_budget_tokens * 4
