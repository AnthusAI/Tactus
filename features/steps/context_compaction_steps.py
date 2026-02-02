from behave import given, when, then

from biblicus.context import ContextPack, ContextPackBlock
from tactus.core.context_assembler import ContextAssembler
from tactus.core.registry import RegistryBuilder
from tactus.core.retrieval import ensure_wikitext2_raw


@given("a Context with a strict token budget and a retriever pack")
def step_context_strict_budget(context):
    ensure_wikitext2_raw()
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
        "support_context",
        {
            "policy": {
                "input_budget": {"max_tokens": 120},
                "overflow": "compact",
            },
            "messages": [
                {"type": "system", "content": "Use this context."},
                {"type": "context", "name": "wikitext_search"},
                {"type": "history"},
                {"type": "user", "content": "Question"},
            ],
        },
    )
    context.registry = builder.registry
    context.context_name = "support_context"
    context.retriever_calls = []


@given("a Context with a tight pack budget and a retriever pack")
def step_context_tight_pack_budget(context):
    ensure_wikitext2_raw()
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
        "support_context",
        {
            "policy": {
                "pack_budget": {"default_max_tokens": 40},
                "overflow": "compact",
            },
            "messages": [
                {"type": "system", "content": "Use this context."},
                {"type": "context", "name": "wikitext_search"},
                {"type": "history"},
                {"type": "user", "content": "Question"},
            ],
        },
    )
    context.registry = builder.registry
    context.context_name = "support_context"
    context.retriever_calls = []


@when("I assemble that Context with compaction")
def step_assemble_context(context):
    def fake_retrieve(request):
        context.retriever_calls.append(
            {
                "query": request.query,
                "split": request.metadata.get("split"),
                "limit": request.limit,
                "maximum_total_characters": request.maximum_total_characters,
            }
        )
        token_budget = request.maximum_total_characters or 0
        token_count = max(1, int(token_budget / 2))
        text = "token " * token_count
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
    context.assembler = assembler
    context.fake_retrieve = fake_retrieve
    context.assembled_context = assembler.assemble(
        context_name=context.context_name,
        base_system_prompt="",
        history_messages=[],
        user_message="",
        template_context={"input": {}, "context": {}},
        retriever_override=fake_retrieve,
    )


@then("the assembled context should fit within the budget")
def step_context_within_budget(context):
    assert context.assembled_context.system_prompt
    assert context.assembled_context.token_count <= 120


@then("the retriever should be re-queried with a smaller budget")
def step_retriever_requery(context):
    assert context.retriever_calls
    assert context.retriever_calls[-1]["maximum_total_characters"] <= 200


@then("the retriever should be re-queried with a tighter budget")
def step_retriever_requery_tighter(context):
    assert context.retriever_calls
    assert len(context.retriever_calls) >= 2
    assert (
        context.retriever_calls[-1]["maximum_total_characters"]
        < context.retriever_calls[0]["maximum_total_characters"]
    )
