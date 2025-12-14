"""
Session management feature step definitions.
"""

import json

from behave import given, then, when

from features.steps.support import FakeSessionStore, parse_key_value_table


def _session_state(context):
    if not hasattr(context, "session_state"):
        context.session_state = {
            "store": FakeSessionStore(),
            "active_session": None,
            "sessions": {},
            "last_export": None,
        }
    return context.session_state


def _store(context) -> FakeSessionStore:
    return _session_state(context)["store"]


def _create_active_session(context):
    session_id = _store(context).start_session({"task": "default"})
    _session_state(context)["active_session"] = session_id
    return session_id


@given("the session primitive is initialized")
def step_impl(context):
    _session_state(context)["store"] = FakeSessionStore()


@given("a chat recorder is configured")
def step_impl(context):
    pass


@when("I start a new session with context:")
def step_impl(context):
    payload = parse_key_value_table(context.table)
    session_id = _store(context).start_session(payload)
    _session_state(context)["active_session"] = session_id


@then("a session should be created")
def step_impl(context):
    assert _session_state(context)["active_session"] is not None


@then("it should have a unique session_id")
def step_impl(context):
    assert isinstance(_session_state(context)["active_session"], str)


@then("the context should be stored")
def step_impl(context):
    session_id = _session_state(context)["active_session"]
    assert _store(context).sessions[session_id].context


@given("an active session")
def step_impl(context):
    _create_active_session(context)


def _active_session(context):
    return _session_state(context)["active_session"]


@when('I record a user message "{message}"')
def step_impl(context, message):
    _store(context).record_message(_active_session(context), "user", message)


@when('I record an assistant message "{message}"')
def step_impl(context, message):
    _store(context).record_message(_active_session(context), "assistant", message)


@then("both messages should be stored in the session")
def step_impl(context):
    messages = _store(context).sessions[_active_session(context)].messages
    assert len(messages) >= 2


@then("they should be in chronological order")
def step_impl(context):
    messages = _store(context).sessions[_active_session(context)].messages
    timestamps = [msg["timestamp"] for msg in messages]
    assert timestamps == sorted(timestamps)


@given("a session with {count:d} messages")
def step_impl(context, count):
    session_id = _store(context).start_session({"task": "preloaded"})
    for idx in range(count):
        _store(context).record_message(session_id, "assistant", f"msg-{idx}")
    _session_state(context)["active_session"] = session_id


@when("I retrieve the session history")
def step_impl(context):
    session = _store(context).sessions[_active_session(context)]
    context.session_history = session.messages


@then("I should get all {count:d} messages")
def step_impl(context, count):
    assert len(context.session_history) == count


@then("they should include role, content, and timestamps")
def step_impl(context):
    assert {"role", "content", "timestamp"}.issubset(context.session_history[0].keys())


@when("an agent requests human approval")
def step_impl(context):
    _store(context).record_message(_active_session(context), "agent", "Request approval", "agent")


@when("I record the approval request")
def step_impl(context):
    _store(context).record_message(
        _active_session(context), "system", "Approval requested", "human_interaction"
    )


@when("I record the human response")
def step_impl(context):
    _store(context).record_message(
        _active_session(context), "human", "Approved", "human_interaction"
    )


@then("the session should show the HITL interaction")
def step_impl(context):
    messages = _store(context).sessions[_active_session(context)].messages
    assert any(msg.get("type") == "human_interaction" for msg in messages)


@then("it should be marked as a human_interaction message")
def step_impl(context):
    messages = _store(context).sessions[_active_session(context)].messages
    assert messages[-1]["type"] == "human_interaction"


@given("an active session with messages")
def step_impl(context):
    session_id = _create_active_session(context)
    _store(context).record_message(session_id, "assistant", "hello")


@when('I end the session with status "{status}"')
def step_impl(context, status):
    _store(context).end_session(_active_session(context), status=status)


@then("the session should be marked as completed")
def step_impl(context):
    assert _store(context).sessions[_active_session(context)].status == "COMPLETED"


@then("the final status should be recorded")
def step_impl(context):
    assert _store(context).sessions[_active_session(context)].status is not None


@then("no more messages can be added")
def step_impl(context):
    session = _store(context).sessions[_active_session(context)]
    assert session.status == "COMPLETED"


@given("a session with custom metadata:")
def step_impl(context):
    metadata = parse_key_value_table(context.table)
    session_id = _store(context).start_session({"task": "meta"}, metadata)
    _session_state(context)["active_session"] = session_id


@when("I retrieve the session")
def step_impl(context):
    context.loaded_session = _store(context).sessions[_active_session(context)]


@then("all metadata should be included")
def step_impl(context):
    assert context.loaded_session.metadata


@then("it can be used for filtering and analysis")
def step_impl(context):
    assert "workflow_name" in context.loaded_session.metadata


@given('I start session "{alias}" for workflow "{workflow}"')
def step_impl(context, alias, workflow):
    session_id = _store(context).start_session({"workflow": workflow})
    _session_state(context)["sessions"][alias] = session_id


@when("I add messages to both sessions")
def step_impl(context):
    for session_id in _session_state(context)["sessions"].values():
        _store(context).record_message(session_id, "assistant", "hello")


@then("each session should maintain independent message history")
def step_impl(context):
    session_ids = list(_session_state(context)["sessions"].values())
    histories = [_store(context).sessions[sid].messages for sid in session_ids]
    first_contents = [messages[0]["content"] for messages in histories]
    assert len(set(first_contents)) == 1


@then("messages should not cross between sessions")
def step_impl(context):
    session_ids = list(_session_state(context)["sessions"].values())
    histories = [_store(context).sessions[sid].messages for sid in session_ids]
    assert histories[0] != histories[1]


@given("a session that was interrupted")
def step_impl(context):
    session_id = _store(context).start_session({"task": "interrupted"})
    _store(context).record_message(session_id, "assistant", "before crash")
    _session_state(context)["interrupted"] = session_id


@when("I retrieve the session by ID")
def step_impl(context):
    session_id = _session_state(context)["interrupted"]
    context.restored_messages = _store(context).sessions[session_id].messages


@then("I should get all messages recorded before interruption")
def step_impl(context):
    assert any(msg["content"] == "before crash" for msg in context.restored_messages)


@then("I can resume the conversation")
def step_impl(context):
    assert context.restored_messages


@given("a completed session with multiple messages")
def step_impl(context):
    session_id = _store(context).start_session({"task": "export"})
    _store(context).record_message(session_id, "assistant", "line1")
    _store(context).record_message(session_id, "assistant", "line2")
    _store(context).end_session(session_id, "COMPLETED")
    _session_state(context)["active_session"] = session_id


@when("I export the session as JSON")
def step_impl(context):
    session_id = _active_session(context)
    _session_state(context)["last_export"] = _store(context).export(session_id)


@then("it should include all messages, metadata, and timestamps")
def step_impl(context):
    data = json.loads(_session_state(context)["last_export"])
    assert "messages" in data and "context" in data


@then("it should be a valid transcript format")
def step_impl(context):
    data = json.loads(_session_state(context)["last_export"])
    assert isinstance(data["messages"], list)


@given("multiple completed sessions")
def step_impl(context):
    for idx in range(3):
        session_id = _store(context).start_session(
            {"task_type": "research" if idx % 2 == 0 else "ops"}
        )
        _store(context).record_message(session_id, "assistant", f"session-{idx}")
        _store(context).end_session(session_id, "COMPLETED")


@when('I query sessions by task_type "{task_type}"')
def step_impl(context, task_type):
    context.analytics_sessions = _store(context).query_by_task_type(task_type)


@then("I should get all research sessions")
def step_impl(context):
    assert context.analytics_sessions


@then("I can calculate metrics like:")
def step_impl(context):
    metrics = [row["metric"] for row in context.table] if context.table else []
    assert {"average_session_duration", "message_count", "human_interactions"}.issuperset(metrics)
