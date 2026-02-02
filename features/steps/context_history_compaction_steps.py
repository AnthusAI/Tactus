from behave import given, when, then

from tactus.core.context_assembler import ContextAssembler
from tactus.core.registry import RegistryBuilder


@given("a Context with a tight history budget")
def step_context_with_history_budget(context):
    builder = RegistryBuilder()
    builder.register_context(
        "support_context",
        {
            "policy": {
                "input_budget": {"max_tokens": 5},
                "overflow": "compact",
            },
            "messages": [
                {"type": "system", "content": "System prompt"},
                {"type": "history"},
                {"type": "user", "content": "User message"},
            ],
        },
    )
    context.registry = builder.registry
    context.context_name = "support_context"
    context.history_messages = [
        {"role": "assistant", "content": "one two"},
        {"role": "assistant", "content": "three four"},
    ]


@when("I assemble that Context with history compaction")
def step_assemble_history_context(context):
    assembler = ContextAssembler(context.registry.contexts)
    context.result = assembler.assemble(
        context_name=context.context_name,
        base_system_prompt="",
        history_messages=context.history_messages,
        user_message="",
        template_context={"input": {}, "context": {}},
    )


@then("the history should be shortened")
def step_history_shortened(context):
    assert len(context.result.history) < len(context.history_messages)
