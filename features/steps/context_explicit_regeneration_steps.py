from behave import given, when, then

from biblicus.context import ContextPack, ContextPackBlock
from tactus.core.context_assembler import ContextAssembler
from tactus.core.registry import RegistryBuilder


@given("an explicit Context with retriever packs and tight budget")
def step_explicit_context_with_budget(context):
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
                "input_budget": {"max_tokens": 10},
                "pack_budget": {"default_ratio": 1.0},
                "overflow": "compact",
                "max_iterations": 3,
            },
            "messages": [
                {"type": "context", "name": "search_primary"},
                {"type": "context", "name": "search_secondary"},
                {"type": "user", "content": "Question"},
            ],
        },
    )
    context.registry = builder.registry
    context.context_name = "support_context"
    context.calls = []


@when("I assemble that explicit Context with regeneration")
def step_assemble_explicit_context(context):
    def fake_retrieve(request):
        context.calls.append(request.maximum_total_characters)
        text = "Valkyria Chronicles III long excerpt" * 5
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


@then("the explicit retrievers should be called with progressively smaller budgets")
def step_explicit_regeneration_calls(context):
    assert len(context.calls) >= 4
    assert context.calls[2] < context.calls[0]
    assert context.calls[3] < context.calls[1]
