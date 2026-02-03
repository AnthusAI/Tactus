from behave import given, when, then

from biblicus.context import ContextPack, ContextPackBlock
from tactus.core.context_assembler import ContextAssembler
from tactus.core.registry import RegistryBuilder


@given("a Context with weighted retriever packs")
def step_context_weighted_packs(context):
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
    builder.register_context(
        "support_context",
        {
            "policy": {
                "input_budget": {"max_tokens": 40},
                "pack_budget": {"default_ratio": 0.5},
            },
            "messages": [
                {"type": "context", "name": "search_primary", "weight": 2.0},
                {"type": "context", "name": "search_secondary", "weight": 1.0},
                {"type": "user", "content": "Question"},
            ],
        },
    )
    context.registry = builder.registry
    context.context_name = "support_context"
    context.calls = []


@when("I assemble that Context with weighted budgets")
def step_assemble_weighted_context(context):
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


@then("the higher-weighted pack should receive a larger budget")
def step_weighted_pack_budget(context):
    assert len(context.calls) >= 2
    assert context.calls[0] > context.calls[1]
