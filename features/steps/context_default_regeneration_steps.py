from behave import given, when, then

from biblicus.context import ContextPack, ContextPackBlock
from tactus.core.context_assembler import ContextAssembler
from tactus.core.registry import RegistryBuilder


@given("a default Context with a retriever pack and tight budget")
def step_default_context_with_budget(context):
    builder = RegistryBuilder()
    builder.register_corpus(
        "wikitext",
        {"split": "train", "maximum_cache_total_items": 2000},
    )
    builder.register_retriever(
        "wikitext_search",
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
                "input_budget": {"max_tokens": 2},
                "overflow": "compact",
                "max_iterations": 3,
            },
            "packs": ["wikitext_search"],
        },
    )
    context.registry = builder.registry
    context.context_name = "support_context"
    context.retriever_calls = []


@when("I assemble that default Context")
def step_assemble_default_context(context):
    def fake_retrieve(request):
        context.retriever_calls.append(request.maximum_total_characters)
        text = "Valkyria Chronicles III long excerpt"
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
        base_system_prompt="System prompt",
        history_messages=[],
        user_message="",
        template_context={"input": {}, "context": {}},
        retriever_override=fake_retrieve,
    )


@then("the retriever should be called with progressively smaller budgets for default Context")
def step_retriever_progressive(context):
    assert len(context.retriever_calls) >= 2
    assert context.retriever_calls[-1] < context.retriever_calls[0]
