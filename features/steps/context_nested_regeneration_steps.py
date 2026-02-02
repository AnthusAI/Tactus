from behave import given, when, then

from biblicus.context import ContextPack, ContextPackBlock
from tactus.core.context_assembler import ContextAssembler
from tactus.core.registry import RegistryBuilder


@given("a nested Context pack with a retriever and tight outer budget")
def step_nested_pack_tight_budget(context):
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
                "overflow": "compact",
                "max_iterations": 3,
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
            "policy": {
                "input_budget": {"max_tokens": 5},
                "overflow": "compact",
                "max_iterations": 3,
            },
            "messages": [
                {
                    "type": "context",
                    "name": "nested_pack",
                    "budget": {"max_tokens": 4},
                },
                {"type": "user", "content": "Question"},
            ],
        },
    )
    context.registry = builder.registry
    context.context_name = "support_context"
    context.calls = []


@when("I assemble the outer Context with regeneration")
def step_assemble_outer_context_with_regeneration(context):
    def fake_retrieve(request):
        context.calls.append(request.maximum_total_characters)
        text = "Nested snippet long" * 10
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


@then("the nested retriever should be called with progressively smaller budgets")
def step_nested_regeneration_calls(context):
    assert len(context.calls) >= 2
    assert context.calls[-1] < context.calls[0]
