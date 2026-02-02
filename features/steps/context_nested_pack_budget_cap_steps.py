from behave import given, when, then

from biblicus.context import ContextPack, ContextPackBlock
from tactus.core.context_assembler import ContextAssembler
from tactus.core.registry import RegistryBuilder


@given("a nested Context pack with a retriever and an outer pack budget")
def step_nested_pack_with_outer_budget(context):
    builder = RegistryBuilder()
    builder.register_corpus(
        "wikitext",
        {"backend_id": "wikitext2", "split": "train", "maximum_cache_total_items": 2000},
    )
    builder.register_retriever(
        "wikitext_search",
        {
            "corpus": "wikitext",
            "query": "Valkyria Chronicles III",
            "limit": 5,
            "maximum_total_characters": 800,
        },
    )
    builder.register_context(
        "nested_pack",
        {
            "policy": {
                "input_budget": {"max_tokens": 50},
                "pack_budget": {"default_ratio": 1.0},
            },
            "messages": [
                {"type": "system", "content": "Nested context"},
                {"type": "context", "name": "wikitext_search"},
            ],
        },
    )
    builder.register_context(
        "support_context",
        {
            "messages": [
                {
                    "type": "context",
                    "name": "nested_pack",
                    "budget": {"max_tokens": 3},
                },
                {"type": "user", "content": "Question"},
            ]
        },
    )
    context.registry = builder.registry
    context.context_name = "support_context"
    context.calls = []


@when("I assemble the outer Context with a budgeted nested pack")
def step_assemble_outer_context_with_budget(context):
    def fake_retrieve(request):
        context.calls.append(request.maximum_total_characters)
        text = "Nested snippet"
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


@then("the nested retriever should receive the capped budget")
def step_nested_pack_budget_cap(context):
    assert len(context.calls) == 1
    assert context.calls[0] <= 12
