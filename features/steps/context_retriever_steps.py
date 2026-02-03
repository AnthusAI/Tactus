from behave import given, when, then

from tactus.core.context_assembler import ContextAssembler
from tactus.core.registry import RegistryBuilder
from tactus.core.retrieval import ensure_wikitext2_raw, retrieve_wikitext2


@given("the Wikitext2 raw dataset is available")
def step_wikitext2_available(context):
    ensure_wikitext2_raw()


@given('a Context with a Wikitext2 retriever for query "{query}"')
def step_context_with_retriever(context, query):
    builder = RegistryBuilder()
    builder.register_corpus(
        "wikitext",
        {
            "split": "train",
            "maximum_cache_total_items": 2000,
        },
    )
    builder.register_retriever(
        "wikitext_search",
        {
            "corpus": "wikitext",
            "retriever_id": "wikitext2",
            "query": query,
            "limit": 3,
            "maximum_total_characters": 400,
        },
    )
    builder.register_context(
        "support_context",
        {
            "messages": [
                {"type": "system", "content": "Use this context."},
                {"type": "context", "name": "wikitext_search"},
                {"type": "history"},
                {"type": "user", "content": "Question."},
            ]
        },
    )
    context.registry = builder.registry
    context.context_name = "support_context"


@when("I assemble that Context")
def step_assemble_context(context):
    assembler = ContextAssembler(
        context.registry.contexts,
        retriever_registry=context.registry.retrievers,
        corpus_registry=context.registry.corpora,
        default_retriever=retrieve_wikitext2,
    )
    assembly = assembler.assemble(
        context_name=context.context_name,
        base_system_prompt="",
        history_messages=[],
        user_message="",
        template_context={"input": {}, "context": {}},
    )
    context.assembled_context = assembly


@then('the assembled context should include "{text}"')
def step_context_contains(context, text):
    assert text in context.assembled_context.system_prompt
