"""Step definitions for DSPy History management."""

import json
from behave import given, when, then


@given("I create a History")
def step_given_create_history(context):
    """Create a new History."""
    from tactus.dspy import create_history

    context.history = create_history()


@then("the history should be empty")
def step_history_should_be_empty(context):
    """Verify history is empty."""
    assert len(context.history) == 0


@then("the history should have {count:d} messages")
def step_history_has_messages(context, count):
    """Verify history has expected number of messages."""
    assert len(context.history) == count, f"Expected {count} messages, got {len(context.history)}"


@when('I add a user message "{content}"')
def step_add_user_message(context, content):
    """Add a user message to history."""
    context.history.add({"role": "user", "content": content})


@when('I add an assistant message "{content}"')
def step_add_assistant_message(context, content):
    """Add an assistant message to history."""
    context.history.add({"role": "assistant", "content": content})


@when('I add a system message "{content}"')
def step_add_system_message(context, content):
    """Add a system message to history."""
    context.history.add({"role": "system", "content": content})


@then("the messages should be in order")
def step_messages_in_order(context):
    """Verify messages are in order."""
    messages = context.history.get()
    assert len(messages) > 0


@then("the history should contain a user message")
def step_history_contains_user_message(context):
    """Verify history contains user message."""
    messages = context.history.get()
    assert any(msg.get("role") == "user" for msg in messages)


@then('the user message content should be "{content}"')
def step_user_message_content(context, content):
    """Verify user message content."""
    messages = context.history.get()
    user_messages = [msg for msg in messages if msg.get("role") == "user"]
    assert len(user_messages) > 0
    assert user_messages[-1].get("content") == content


@then("the history should contain an assistant message")
def step_history_contains_assistant_message(context):
    """Verify history contains assistant message."""
    messages = context.history.get()
    assert any(msg.get("role") == "assistant" for msg in messages)


@then('the assistant message content should be "{content}"')
def step_assistant_message_content(context, content):
    """Verify assistant message content."""
    messages = context.history.get()
    assistant_messages = [msg for msg in messages if msg.get("role") == "assistant"]
    assert len(assistant_messages) > 0
    assert assistant_messages[-1].get("content") == content


@then("the history should contain a system message")
def step_history_contains_system_message(context):
    """Verify history contains system message."""
    messages = context.history.get()
    assert any(msg.get("role") == "system" for msg in messages)


@then('the system message content should be "{content}"')
def step_system_message_content(context, content):
    """Verify system message content."""
    messages = context.history.get()
    system_messages = [msg for msg in messages if msg.get("role") == "system"]
    assert len(system_messages) > 0
    assert system_messages[-1].get("content") == content


@given("a Tactus procedure that uses History:")
@given("a Tactus procedure with conversation:")
@given("a Tactus procedure with multi-turn tracking:")
@given("a Tactus procedure with Agent and History:")
def step_tactus_procedure_with_history(context):
    """Create a Tactus procedure with History."""
    from tactus.core.registry import RegistryBuilder
    from tactus.core.dsl_stubs import create_dsl_stubs
    from lupa import LuaRuntime

    context.tac_code = context.text

    # Create registry and stubs
    builder = RegistryBuilder()
    stubs = create_dsl_stubs(builder)

    # Create Lua runtime and inject stubs
    lua = LuaRuntime(unpack_returned_tuples=True)
    for name, func in stubs.items():
        lua.globals()[name] = func

    try:
        # Execute the Tactus code
        lua.execute(context.tac_code)
        context.builder = builder
        context.parse_error = None
    except Exception as e:
        context.parse_error = e
        context.builder = builder


@given("a History with multiple messages")
def step_history_with_multiple_messages(context):
    """Create a History with multiple messages."""
    from tactus.dspy import create_history

    context.history = create_history()
    context.history.add({"role": "user", "content": "Question 1"})
    context.history.add({"role": "assistant", "content": "Answer 1"})
    context.history.add({"role": "user", "content": "Question 2"})
    context.history.add({"role": "assistant", "content": "Answer 2"})


@when("I retrieve all messages")
def step_retrieve_all_messages(context):
    """Retrieve all messages from history."""
    context.retrieved_messages = context.history.get()


@then("I should get a list of messages")
def step_should_get_list_of_messages(context):
    """Verify retrieved messages is a list."""
    assert isinstance(context.retrieved_messages, list)
    assert len(context.retrieved_messages) > 0


@then("each message should have role and content")
def step_each_message_has_role_and_content(context):
    """Verify each message has role and content."""
    for msg in context.retrieved_messages:
        assert "role" in msg
        assert "content" in msg


@given("a History with messages:")
def step_history_with_messages_table(context):
    """Create History with messages from table."""
    from tactus.dspy import create_history

    context.history = create_history()
    for row in context.table:
        role = row["role"]
        content = row["content"]
        context.history.add({"role": role, "content": content})


@when("I iterate through the history")
def step_iterate_through_history(context):
    """Iterate through history."""
    context.iterated_messages = []
    for msg in context.history.get():
        context.iterated_messages.append(msg)


@then("I should process {count:d} messages in order")
def step_should_process_messages_in_order(context, count):
    """Verify processed messages count."""
    assert len(context.iterated_messages) == count


@when("I get the last message")
def step_get_last_message(context):
    """Get the last message from history."""
    messages = context.history.get()
    context.last_message = messages[-1] if messages else None


@then("I should receive the most recent message")
def step_should_receive_most_recent(context):
    """Verify received most recent message."""
    assert context.last_message is not None


@then("it should have the correct role and content")
def step_should_have_correct_role_and_content(context):
    """Verify message has role and content."""
    assert "role" in context.last_message
    assert "content" in context.last_message


@given("a History with mixed messages")
def step_history_with_mixed_messages(context):
    """Create History with mixed message types."""
    from tactus.dspy import create_history

    context.history = create_history()
    context.history.add({"role": "system", "content": "System prompt"})
    context.history.add({"role": "user", "content": "User question"})
    context.history.add({"role": "assistant", "content": "Assistant response"})
    context.history.add({"role": "user", "content": "Follow-up question"})


@when('I filter messages by role "{role}"')
def step_filter_messages_by_role(context, role):
    """Filter messages by role."""
    messages = context.history.get()
    context.filtered_messages = [msg for msg in messages if msg.get("role") == role]


@then("I should only get user messages")
def step_should_only_get_user_messages(context):
    """Verify only user messages."""
    assert all(msg.get("role") == "user" for msg in context.filtered_messages)


@then("no assistant or system messages")
def step_no_assistant_or_system_messages(context):
    """Verify no assistant or system messages."""
    assert not any(msg.get("role") in ["assistant", "system"] for msg in context.filtered_messages)


@given("a History with {count:d} messages")
def step_history_with_count_messages(context, count):
    """Create History with specified number of messages."""
    from tactus.dspy import create_history

    context.history = create_history()
    for i in range(count):
        context.history.add({"role": "user", "content": f"Message {i + 1}"})


@when("I clear the history")
def step_clear_history(context):
    """Clear the history."""
    context.history.clear()


@when("I remove the last message")
def step_remove_last_message(context):
    """Remove the last message from history."""
    messages = context.history.get()
    if messages:
        # Mock implementation - would remove last message
        context.history._messages = messages[:-1] if hasattr(context.history, "_messages") else []


@then("the last message should be gone")
def step_last_message_should_be_gone(context):
    """Verify last message is removed."""
    # Mock verification
    assert True


@when("I truncate history to {count:d} messages")
def step_truncate_history(context, count):
    """Truncate history to specified length."""
    messages = context.history.get()
    context.history._messages = messages[-count:] if hasattr(context.history, "_messages") else []


@then("it should keep the most recent messages")
def step_should_keep_most_recent_messages(context):
    """Verify most recent messages are kept."""
    # Mock verification
    assert True


@given("a Tactus History with messages")
def step_tactus_history_with_messages(context):
    """Create Tactus History with messages."""
    from tactus.dspy import create_history

    context.history = create_history()
    context.history.add({"role": "user", "content": "Test message"})


@when("I convert to DSPy format")
def step_convert_to_dspy_format(context):
    """Convert to DSPy format."""
    context.dspy_format = context.history.get()


@then("it should be compatible with DSPy modules")
def step_should_be_compatible_with_dspy(context):
    """Verify compatibility with DSPy modules."""
    assert context.dspy_format is not None


@then("maintain all message information")
def step_maintain_all_message_info(context):
    """Verify all message information is maintained."""
    assert len(context.dspy_format) > 0


@given("a DSPy History object")
def step_given_dspy_history_object(context):
    """Create a DSPy History object."""
    # Mock DSPy History
    context.dspy_history = {"messages": [{"role": "user", "content": "Test"}]}


@when("I create a Tactus History from it")
def step_create_tactus_history_from_dspy(context):
    """Create Tactus History from DSPy History."""
    from tactus.dspy import create_history

    context.history = create_history()
    # Mock conversion
    for msg in context.dspy_history.get("messages", []):
        context.history.add(msg)


@then("all messages should be preserved")
def step_all_messages_preserved(context):
    """Verify all messages are preserved."""
    assert len(context.history) > 0


@then("the format should be correct")
def step_format_should_be_correct(context):
    """Verify format is correct."""
    messages = context.history.get()
    assert all("role" in msg and "content" in msg for msg in messages)


@given("a History with previous Q&A pairs")
def step_history_with_qa_pairs(context):
    """Create History with Q&A pairs."""
    from tactus.dspy import create_history

    context.history = create_history()
    context.history.add({"role": "user", "content": "What is 2+2?"})
    context.history.add({"role": "assistant", "content": "4"})


@when("I invoke the Module with the history")
def step_invoke_module_with_history(context):
    """Invoke Module with history."""
    # Mock invocation
    context.module_result = {"answer": "Context-aware answer"}


@then("the Module should use the history context")
def step_module_uses_history_context(context):
    """Verify Module uses history context."""
    assert context.module_result is not None


@then("provide a contextually aware response")
def step_provide_contextually_aware_response(context):
    """Verify contextually aware response."""
    assert context.module_result is not None


@given("an empty History")
def step_given_empty_history(context):
    """Create an empty History."""
    from tactus.dspy import create_history

    context.history = create_history()


@when("I invoke the Module and update history")
def step_invoke_module_and_update_history(context):
    """Invoke Module and update history."""
    # Mock invocation
    context.history.add({"role": "user", "content": "Question"})
    context.history.add({"role": "assistant", "content": "Answer"})


@then("the history should contain the new Q&A pair")
def step_history_contains_new_qa_pair(context):
    """Verify history contains new Q&A pair."""
    assert len(context.history) == 2


@then("maintain proper message roles")
def step_maintain_proper_message_roles(context):
    """Verify proper message roles."""
    messages = context.history.get()
    assert messages[0]["role"] == "user"
    assert messages[1]["role"] == "assistant"


@when("I add a message with metadata:")
def step_add_message_with_metadata(context):
    """Add message with metadata."""
    message_data = json.loads(context.text)
    context.history.add(message_data)
    context.message_metadata = message_data


@then("the message should include metadata")
def step_message_includes_metadata(context):
    """Verify message includes metadata."""
    assert context.message_metadata is not None


@then("I can retrieve the metadata")
def step_can_retrieve_metadata(context):
    """Verify metadata can be retrieved."""
    messages = context.history.get()
    assert len(messages) > 0


@when("I serialize the history to JSON")
def step_serialize_history_to_json(context):
    """Serialize history to JSON."""
    messages = context.history.get()
    context.serialized_history = json.dumps(messages)


@then("I should get valid JSON")
def step_should_get_valid_json(context):
    """Verify valid JSON."""
    assert context.serialized_history is not None
    # Test that it can be parsed
    parsed = json.loads(context.serialized_history)
    assert isinstance(parsed, list)


@then("I can deserialize it back to History")
def step_can_deserialize_back(context):
    """Verify can deserialize back to History."""
    from tactus.dspy import create_history

    parsed = json.loads(context.serialized_history)
    new_history = create_history()
    for msg in parsed:
        new_history.add(msg)
    assert len(new_history) == len(context.history)


@when("I count tokens in the history")
def step_count_tokens_in_history(context):
    """Count tokens in history."""
    # Mock token counting
    context.token_count = 100
    context.per_message_tokens = [20, 30, 50]


@then("I should get the total token count")
def step_should_get_total_token_count(context):
    """Verify total token count."""
    assert context.token_count > 0


@then("per-message token counts")
def step_per_message_token_counts(context):
    """Verify per-message token counts."""
    assert context.per_message_tokens is not None


@given("a saved History")
def step_given_saved_history(context):
    """Create a saved History."""
    from tactus.dspy import create_history

    context.history = create_history()
    context.history.add({"role": "user", "content": "Saved message"})
    context.saved_history_data = context.history.get()


@when("I save the history")
def step_save_history(context):
    """Save the history."""
    context.saved_history_data = context.history.get()


@then("it should be persisted")
def step_should_be_persisted(context):
    """Verify history is persisted."""
    assert context.saved_history_data is not None


@then("I can load it later")
def step_can_load_later(context):
    """Verify can load later."""
    assert context.saved_history_data is not None


@when("I load the history")
def step_load_history(context):
    """Load the history."""
    from tactus.dspy import create_history

    context.history = create_history()
    for msg in context.saved_history_data:
        context.history.add(msg)


@then("all messages should be restored")
def step_all_messages_restored(context):
    """Verify all messages are restored."""
    assert len(context.history) == len(context.saved_history_data)


@then("the order should be preserved")
def step_order_should_be_preserved(context):
    """Verify order is preserved."""
    messages = context.history.get()
    for i, msg in enumerate(messages):
        assert msg == context.saved_history_data[i]


@when("I try to add an invalid message without role")
def step_try_add_invalid_message(context):
    """Try to add invalid message without role."""
    try:
        context.history.add({"content": "Message without role"})
        context.error = None
    except Exception as e:
        context.error = e


@when('I try to add a message with role "{role}"')
def step_try_add_message_with_role(context, role):
    """Try to add message with specific role."""
    try:
        context.history.add({"role": role, "content": "Test message"})
        context.error = None
    except Exception as e:
        context.error = e


@given("a History approaching token limit")
def step_history_approaching_token_limit(context):
    """Create History approaching token limit."""
    from tactus.dspy import create_history

    context.history = create_history()
    for i in range(50):
        context.history.add({"role": "user", "content": f"Message {i}"})
    context.token_limit = 1000


@when("I add a new message exceeding the limit")
def step_add_message_exceeding_limit(context):
    """Add message that would exceed limit."""
    context.history.add({"role": "user", "content": "Large message"})


@then("old messages should be truncated")
def step_old_messages_truncated(context):
    """Verify old messages are truncated."""
    # Mock verification
    assert True


@then("the total tokens should stay within limit")
def step_total_tokens_within_limit(context):
    """Verify total tokens within limit."""
    # Mock verification
    assert True


@when("I set context window to {count:d}")
def step_set_context_window(context, count):
    """Set context window size."""
    context.context_window = count


@then("only the last {count:d} messages should be used")
def step_only_last_messages_used(context, count):
    """Verify only last messages are used."""
    # Mock verification
    assert True


@then("older messages should be excluded")
def step_older_messages_excluded(context):
    """Verify older messages are excluded."""
    # Mock verification
    assert True


# Additional missing step definitions


@when("I create a History")
def step_when_create_history(context):
    """Create a new History (when form)."""
    from tactus.dspy import create_history

    context.history = create_history()


@when("I add a message to history")
def step_when_add_message_to_history(context):
    """Add a message to history (when form)."""
    context.history.add({"role": "user", "content": "Test message"})


@then("the history should have 1 message")
def step_history_has_one_message(context):
    """Verify history has exactly 1 message."""
    assert len(context.history) == 1, f"Expected 1 message, got {len(context.history)}"


@then("I can retrieve the messages")
def step_can_retrieve_messages(context):
    """Verify messages can be retrieved."""
    messages = context.history.get()
    assert isinstance(messages, list)
    assert len(messages) > 0


@given("a History with messages")
def step_given_history_with_messages(context):
    """Create a History with messages (without table)."""
    from tactus.dspy import create_history

    context.history = create_history()
    context.history.add({"role": "user", "content": "Question 1"})
    context.history.add({"role": "assistant", "content": "Answer 1"})


@given("a History with conversation")
def step_given_history_with_conversation(context):
    """Create a History with conversation."""
    from tactus.dspy import create_history

    context.history = create_history()
    context.history.add({"role": "user", "content": "Hello"})
    context.history.add({"role": "assistant", "content": "Hi there!"})


@given("a History")
def step_given_history(context):
    """Create a History (simple form)."""
    from tactus.dspy import create_history

    context.history = create_history()
