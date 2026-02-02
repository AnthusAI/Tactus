from behave import given, when, then

from biblicus.context import ContextPack, ContextPackBlock
from tactus.core.context_assembler import ContextAssembler
from tactus.core.registry import RegistryBuilder


@given("a Context with an expandable retriever pack")
def step_expandable_retriever_pack(context):
    builder = RegistryBuilder()
    builder.register_retriever(
        "paged_retriever",
        {
            "query": "expandable",
            "limit": 2,
            "maximum_total_characters": 400,
        },
    )
    builder.register_context(
        "support_context",
        {
            "policy": {
                "input_budget": {"max_tokens": 50},
                "pack_budget": {"default_ratio": 1.0},
                "overflow": "compact",
                "expansion": {"max_pages": 3, "min_fill_ratio": 1.0},
            },
            "messages": [
                {"type": "system", "content": "Use this context."},
                {"type": "context", "name": "paged_retriever"},
                {"type": "user", "content": "Question"},
            ],
        },
    )
    context.registry = builder.registry
    context.context_name = "support_context"
    context.retriever_calls = []


@when("I assemble that Context with expansion")
def step_assemble_context_with_expansion(context):
    def fake_retrieve(request):
        context.retriever_calls.append(request.offset)
        token_count = request.limit * 2
        text = "token " * token_count
        return ContextPack(
            text=text,
            evidence_count=request.limit,
            blocks=[
                ContextPackBlock(
                    evidence_item_id=f"page-{request.offset}",
                    text=text,
                    metadata=None,
                )
            ],
        )

    assembler = ContextAssembler(
        context.registry.contexts,
        retriever_registry=context.registry.retrievers,
    )
    context.assembled = assembler.assemble(
        context_name=context.context_name,
        base_system_prompt="",
        history_messages=[],
        user_message="",
        template_context={"input": {}, "context": {}},
        retriever_override=fake_retrieve,
    )


@then("the retriever should be called with paginated offsets")
def step_verify_pagination(context):
    assert context.retriever_calls == [0, 2, 4]


@then("the assembled context should include expanded content")
def step_verify_expanded_content(context):
    assert context.assembled.system_prompt.count("token") >= 12
