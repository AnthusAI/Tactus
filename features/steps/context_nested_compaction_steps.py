from behave import given, when, then

from tactus.core.context_assembler import ContextAssembler
from tactus.core.registry import RegistryBuilder


@given("a Context with a nested pack and a tight pack budget")
def step_nested_context_with_budget(context):
    builder = RegistryBuilder()
    builder.register_context(
        "nested_pack",
        {
            "messages": [
                {"type": "system", "content": "one two three four five"},
            ]
        },
    )
    builder.register_context(
        "support_context",
        {
            "messages": [
                {"type": "system", "content": "Use this."},
                {"type": "context", "name": "nested_pack", "budget": {"max_tokens": 3}},
                {"type": "user", "content": "Question"},
            ],
            "policy": {
                "overflow": "compact",
            },
        },
    )
    context.registry = builder.registry
    context.context_name = "support_context"


@when("I assemble that Context with nested compaction")
def step_assemble_nested_context(context):
    assembler = ContextAssembler(context.registry.contexts)
    context.result = assembler.assemble(
        context_name=context.context_name,
        base_system_prompt="",
        history_messages=[],
        user_message="",
        template_context={"input": {}, "context": {}},
    )


@then("the nested context should be compacted")
def step_nested_compacted(context):
    assert "one two three" in context.result.system_prompt
    assert "four" not in context.result.system_prompt
