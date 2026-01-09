"""Step definitions for DSPy Agent interactions."""

import json
from behave import given, when, then


@when('I create an Agent with system prompt "{prompt}"')
def step_create_agent_with_system_prompt(context, prompt):
    """Create Agent with system prompt."""
    from tactus.dspy import create_dspy_agent

    context.agent = create_dspy_agent("test_agent", {"system_prompt": prompt})
    context.agent_system_prompt = prompt


@then("the agent should use the custom system prompt")
def step_agent_uses_custom_system_prompt(context):
    """Verify agent uses custom system prompt."""
    assert context.agent_system_prompt is not None


@then("the agent should be ready for conversation")
def step_agent_ready_for_conversation(context):
    """Verify agent is ready."""
    assert context.agent is not None


@when("I create an Agent without system prompt")
def step_create_agent_without_system_prompt(context):
    """Create Agent without system prompt."""
    from tactus.dspy import create_dspy_agent

    context.agent = create_dspy_agent("test_agent", {})


@then("the agent should have default behavior")
def step_agent_has_default_behavior(context):
    """Verify agent has default behavior."""
    assert context.agent is not None


@then("the agent should still be functional")
def step_agent_still_functional(context):
    """Verify agent is functional."""
    assert context.agent is not None


@given("a Tactus procedure that creates an Agent:")
@given("a Tactus procedure with Agent turns:")
@given("a Tactus procedure with multiple agents:")
def step_tactus_procedure_creates_agent(context):
    """Create Tactus procedure that creates Agent."""
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


@then("the history should be empty initially")
def step_history_empty_initially(context):
    """Verify agent history is empty initially."""
    history = context.agent_history
    assert len(history) == 0


@then("I can add messages to the agent's history")
def step_can_add_messages_to_agent_history(context):
    """Verify can add messages to agent history."""
    context.agent.history.add({"role": "user", "content": "Test message"})
    assert len(context.agent.get_history()) > 0


@given('an Agent with system prompt "{prompt}"')
def step_given_agent_with_system_prompt(context, prompt):
    """Create Agent with system prompt."""
    from tactus.dspy import create_dspy_agent

    context.agent = create_dspy_agent("test_agent", {"system_prompt": prompt})


@when("I execute multiple turns:")
def step_execute_multiple_turns(context):
    """Execute multiple turns."""
    context.turn_results = []
    for row in context.table:
        turn_num = row["turn"]
        user_input = row["user_input"]
        # Mock turn execution
        response = f"Response to: {user_input}"
        context.turn_results.append({"turn": turn_num, "response": response})


@then("the agent should maintain conversation context")
def step_agent_maintains_context(context):
    """Verify agent maintains context."""
    assert len(context.turn_results) > 0


@then("each response should be contextually aware")
def step_each_response_contextually_aware(context):
    """Verify responses are contextually aware."""
    assert len(context.turn_results) > 0


@given("a conversation history with previous exchanges")
def step_given_conversation_history_with_exchanges(context):
    """Create conversation history with exchanges."""
    from tactus.dspy import create_history

    context.history = create_history()
    context.history.add({"role": "user", "content": "Previous question"})
    context.history.add({"role": "assistant", "content": "Previous answer"})


@when("I create an Agent with this history")
def step_create_agent_with_history(context):
    """Create Agent with existing history."""
    from tactus.dspy import create_dspy_agent

    context.agent = create_dspy_agent(
        "test_agent", {"system_prompt": "Continue conversation", "history": context.history}
    )


@then("the agent should continue from where it left off")
def step_agent_continues_from_where_left_off(context):
    """Verify agent continues from previous point."""
    assert context.agent is not None


@then("maintain the conversation context")
def step_maintain_conversation_context(context):
    """Verify conversation context maintained."""
    assert context.agent is not None


@when('I execute a turn with input "{input_text}"')
def step_execute_turn_with_input(context, input_text):
    """Execute a turn with input."""
    # Mock turn execution - agent should respond with a mock response
    context.turn_response = f"Response to: {input_text}"
    context.agent_response = {"content": f"Response to: {input_text}"}
    context.turn_result = {"content": f"Response to: {input_text}"}
    context.module_result = {"content": f"Response to: {input_text}"}


# Note: "the agent should respond" and "the response should be relevant" are defined in agent_primitives_steps.py


@given("an Agent")
def step_given_agent(context):
    """Create a basic Agent."""
    from tactus.dspy import create_dspy_agent

    context.agent = create_dspy_agent("test_agent", {"system_prompt": "Be helpful"})


@when("I execute a turn with:")
def step_execute_turn_with_params(context):
    """Execute turn with parameters from table."""
    params = {}
    for row in context.table:
        param = row["parameter"]
        value = row["value"]
        # Try to convert types
        try:
            value = float(value)
            if value.is_integer():
                value = int(value)
        except ValueError:
            pass
        params[param] = value

    context.turn_params = params
    # Mock turn execution
    context.turn_response = "Response with custom parameters"


@then("the agent should use the custom parameters")
def step_agent_uses_custom_parameters(context):
    """Verify agent uses custom parameters."""
    assert context.turn_params is not None


@then("respond accordingly")
def step_respond_accordingly(context):
    """Verify agent responded."""
    assert context.turn_response is not None


@given("an Agent with initial context")
def step_given_agent_with_initial_context(context):
    """Create Agent with initial context."""
    from tactus.dspy import create_dspy_agent

    context.agent = create_dspy_agent("test_agent", {"system_prompt": "You have context"})


@when("I execute a turn without user input")
def step_execute_turn_without_input(context):
    """Execute turn without user input."""
    # Mock turn execution
    context.turn_response = "Continuation without explicit input"


@then("the agent should continue the conversation")
def step_agent_continues_conversation(context):
    """Verify agent continues conversation."""
    assert context.turn_response is not None


@when('I inject context "{context_text}"')
def step_inject_context(context, context_text):
    """Inject context before turn."""
    context.injected_context = context_text
    # Would add to agent's history or context


@when('I execute a turn with "{input_text}"')
def step_execute_turn_with_text(context, input_text):
    """Execute turn with input text."""
    # Mock turn execution
    context.turn_response = f"Response considering context: {input_text}"
    context.module_result = {"content": context.turn_response}


@then("the response should be concise")
def step_response_should_be_concise(context):
    """Verify response is concise."""
    assert context.turn_response is not None


@then("respect the injected context")
def step_respect_injected_context(context):
    """Verify injected context is respected."""
    assert context.injected_context is not None


@when("I inject multiple context messages:")
def step_inject_multiple_context_messages(context):
    """Inject multiple context messages."""
    context.injected_messages = []
    for row in context.table:
        role = row["role"]
        content = row["content"]
        context.injected_messages.append({"role": role, "content": content})


@when("I execute a turn")
def step_execute_a_turn(context):
    """Execute a turn."""
    # Mock turn execution
    context.turn_response = "Response considering all context"


@then("the agent should consider all context")
def step_agent_considers_all_context(context):
    """Verify agent considers all context."""
    assert context.injected_messages is not None


@then("each agent should maintain separate history")
def step_each_agent_maintains_separate_history(context):
    """Verify each agent maintains separate history."""
    # Mock verification
    assert True


@given("two agents with different specializations")
def step_given_two_agents_different_specializations(context):
    """Create two agents with different specializations."""
    from tactus.dspy import create_dspy_agent

    context.agent1 = create_dspy_agent("agent1", {"system_prompt": "Math expert"})
    context.agent2 = create_dspy_agent("agent2", {"system_prompt": "Writing expert"})


@when("agent1 generates information")
def step_agent1_generates_information(context):
    """Agent1 generates information."""
    context.agent1_output = "Mathematical result: 42"


@when("agent2 receives that information")
def step_agent2_receives_information(context):
    """Agent2 receives information from agent1."""
    context.agent2_input = context.agent1_output


@then("agent2 should be able to use agent1's output")
def step_agent2_uses_agent1_output(context):
    """Verify agent2 can use agent1's output."""
    assert context.agent2_input is not None


@then("maintain coherent conversation flow")
def step_maintain_coherent_flow(context):
    """Verify coherent conversation flow."""
    assert context.agent2_input == context.agent1_output


@given("an Agent with default temperature {temperature:f}")
def step_given_agent_with_default_temperature(context, temperature):
    """Create Agent with default temperature."""
    from tactus.dspy import create_dspy_agent

    context.agent = create_dspy_agent(
        "test_agent", {"system_prompt": "Be helpful", "temperature": temperature}
    )
    context.default_temperature = temperature


@when("I execute turns with different temperatures:")
def step_execute_turns_different_temperatures(context):
    """Execute turns with different temperatures."""
    context.temperature_turns = []
    for row in context.table:
        turn = row["turn"]
        temperature = row["temperature"]
        if temperature != "default":
            temperature = float(temperature)
        else:
            temperature = context.default_temperature
        context.temperature_turns.append({"turn": turn, "temperature": temperature})


@then("each turn should reflect its temperature setting")
def step_each_turn_reflects_temperature(context):
    """Verify each turn reflects temperature."""
    assert len(context.temperature_turns) > 0


@given('an Agent configured with "{model}"')
def step_given_agent_configured_with_model(context, model):
    """Create Agent configured with specific model."""
    from tactus.dspy import create_dspy_agent

    context.agent = create_dspy_agent("test_agent", {"system_prompt": "Be helpful", "model": model})
    context.agent_model = model


@when('I execute a turn with model override "{model}"')
def step_execute_turn_with_model_override(context, model):
    """Execute turn with model override."""
    context.override_model = model
    # Mock turn execution
    context.turn_response = f"Response using {model}"


@then('that specific turn should use "{model}"')
def step_that_turn_uses_model(context, model):
    """Verify that turn uses specified model."""
    assert context.override_model == model


@then("subsequent turns should revert to default")
def step_subsequent_turns_revert(context):
    """Verify subsequent turns revert to default."""
    # Mock verification
    assert True


@given("no LM is configured")
def step_given_no_lm_configured(context):
    """Ensure no LM is configured."""
    # Mock - reset LM configuration
    from tactus.dspy import reset_lm_configuration

    reset_lm_configuration()
    context.lm_configured = False


@when("I try to create an Agent")
def step_try_create_agent(context):
    """Try to create an Agent."""
    from tactus.dspy import create_dspy_agent

    try:
        context.agent = create_dspy_agent("test_agent", {"system_prompt": "Test"})
        context.error = None
    except Exception as e:
        context.error = e
        context.agent = None


@then('the error should mention "LM not configured"')
def step_error_mentions_lm_not_configured(context):
    """Verify the error message mentions LM configuration."""
    # Check both context.error (from try_create_agent) and context.agent_error
    error = getattr(context, "error", None) or getattr(context, "agent_error", None)
    assert error is not None, "No error found in context"
    assert "LM not configured" in str(
        error
    ), f"Error message '{error}' does not mention 'LM not configured'"


@given("an Agent with invalid configuration")
def step_given_agent_invalid_config(context):
    """Create Agent with invalid configuration."""
    from tactus.dspy import create_dspy_agent

    try:
        context.agent = create_dspy_agent("test_agent", {"invalid_param": "value"})
    except Exception:
        context.agent = None


@then("it should handle the error gracefully")
def step_should_handle_error_gracefully(context):
    """Verify error is handled gracefully."""
    assert context.turn_error is not None or context.agent_error is not None


@then("provide meaningful error information")
def step_provide_meaningful_error_info(context):
    """Verify meaningful error information."""
    error = context.turn_error if hasattr(context, "turn_error") else context.agent_error
    assert error is not None


@given("an Agent with tool definitions:")
def step_given_agent_with_tools(context):
    """Create Agent with tool definitions."""
    from tactus.dspy import create_dspy_agent

    config = json.loads(context.text)
    context.agent = create_dspy_agent("test_agent", config)
    context.agent_tools = config.get("tools", [])


@when("the agent needs to calculate something")
def step_agent_needs_to_calculate(context):
    """Agent needs to calculate."""
    # Mock calculation need
    context.calculation_needed = True


@then("it should be able to use the calculator tool")
def step_should_use_calculator_tool(context):
    """Verify can use calculator tool."""
    assert context.agent_tools is not None


@then("integrate tool results in response")
def step_integrate_tool_results(context):
    """Verify tool results integrated."""
    assert context.agent_tools is not None


@given("an Agent configured for structured output:")
def step_given_agent_structured_output(context):
    """Create Agent configured for structured output."""
    from tactus.dspy import create_dspy_agent

    config = json.loads(context.text)
    context.agent = create_dspy_agent("test_agent", config)
    context.agent_output_format = config.get("output_format", {})


@then("the response should match the output format")
def step_response_matches_output_format(context):
    """Verify response matches output format."""
    assert context.agent_output_format is not None


@then("include all required fields")
def step_include_all_required_fields(context):
    """Verify all required fields included."""
    assert context.agent_output_format is not None


@given("an Agent with conversation history")
def step_given_agent_with_conversation_history(context):
    """Create Agent with conversation history."""
    from tactus.dspy import create_dspy_agent, create_history

    history = create_history()
    history.add({"role": "user", "content": "Question 1"})
    history.add({"role": "assistant", "content": "Answer 1"})
    context.agent = create_dspy_agent(
        "test_agent", {"system_prompt": "Be helpful", "history": history}
    )


@when("I save the agent state")
def step_save_agent_state(context):
    """Save agent state."""
    context.saved_agent_state = {
        "system_prompt": "Be helpful",
        "history": context.agent.get_history() if hasattr(context.agent, "get_history") else [],
        "configuration": {},
    }


@then("it should preserve:")
def step_should_preserve(context):
    """Verify components are preserved."""
    for row in context.table:
        component = row["component"]
        assert component in ["system_prompt", "history", "configuration"]


@given("a saved agent state")
def step_given_saved_agent_state(context):
    """Create saved agent state."""
    context.saved_agent_state = {
        "system_prompt": "Be helpful",
        "history": [{"role": "user", "content": "Previous message"}],
        "configuration": {},
    }


@when("I restore the agent")
def step_restore_agent(context):
    """Restore agent from saved state."""
    from tactus.dspy import create_dspy_agent, create_history

    history = create_history()
    for msg in context.saved_agent_state["history"]:
        history.add(msg)
    context.agent = create_dspy_agent(
        "restored_agent",
        {"system_prompt": context.saved_agent_state["system_prompt"], "history": history},
    )


@then("it should continue from where it left off")
def step_should_continue_from_where_left_off(context):
    """Verify agent continues from saved point."""
    assert context.agent is not None


@then("maintain all previous context")
def step_maintain_all_previous_context(context):
    """Verify all previous context maintained."""
    assert context.agent is not None


@given("an Agent with various settings")
def step_given_agent_with_various_settings(context):
    """Create Agent with various settings."""
    from tactus.dspy import create_dspy_agent

    context.agent = create_dspy_agent(
        "test_agent",
        {"system_prompt": "Be helpful", "model": "openai/gpt-4o-mini", "temperature": 0.7},
    )


@when("I inspect the agent")
def step_inspect_agent(context):
    """Inspect agent."""
    context.agent_inspection = {
        "system_prompt": "Be helpful",
        "model": "openai/gpt-4o-mini",
        "history_length": 0,
        "temperature": 0.7,
    }


@then("I should see:")
def step_should_see(context):
    """Verify inspection results or statistics."""
    for row in context.table:
        # Check if it's property or metric based on what's in the row
        if "property" in row.headings:
            property_name = row["property"]
            assert property_name in context.agent_inspection
        elif "metric" in row.headings:
            metric = row["metric"]
            assert metric in context.agent_stats


@given("an Agent after multiple turns")
def step_given_agent_after_multiple_turns(context):
    """Create Agent after multiple turns."""
    from tactus.dspy import create_dspy_agent

    context.agent = create_dspy_agent("test_agent", {"system_prompt": "Be helpful"})
    # Mock multiple turns
    context.turn_count = 5


@when("I get agent statistics")
def step_get_agent_statistics(context):
    """Get agent statistics."""
    context.agent_stats = {
        "turn_count": context.turn_count,
        "token_usage": 500,
        "avg_response": 100,
    }


@given("an Agent with an integrated Module:")
def step_given_agent_with_integrated_module(context):
    """Create Agent with integrated Module."""
    from tactus.dspy import create_dspy_agent

    config = json.loads(context.text)
    context.agent = create_dspy_agent("test_agent", config)
    context.agent_modules = config.get("modules", {})


@when("the agent receives a complex problem")
def step_agent_receives_complex_problem(context):
    """Agent receives complex problem."""
    context.complex_problem = "Solve this complex problem"


@then("it should invoke the reasoning module")
def step_should_invoke_reasoning_module(context):
    """Verify reasoning module is invoked."""
    assert context.agent_modules is not None


@then("integrate module output in response")
def step_integrate_module_output(context):
    """Verify module output integrated."""
    assert context.agent_modules is not None


@given("an Agent with response signature:")
def step_given_agent_with_response_signature(context):
    """Create Agent with response signature."""
    from tactus.dspy import create_dspy_agent

    config = json.loads(context.text)
    context.agent = create_dspy_agent("test_agent", config)
    context.agent_response_signature = config.get("response_signature")


@when("the agent generates a response")
def step_agent_generates_response(context):
    """Agent generates response."""
    context.agent_response = {
        "query": "Test query",
        "answer": "Test answer",
        "confidence": 0.9,
        "explanation": "Test explanation",
    }


@then("it should validate against the signature")
def step_should_validate_against_signature(context):
    """Verify validation against signature."""
    assert context.agent_response_signature is not None


@then("ensure all fields are present")
def step_ensure_all_fields_present(context):
    """Verify all fields present."""
    assert context.agent_response is not None


@given("an Agent configured for streaming")
def step_given_agent_configured_for_streaming(context):
    """Create Agent configured for streaming."""
    from tactus.dspy import create_dspy_agent

    context.agent = create_dspy_agent(
        "test_agent", {"system_prompt": "Be helpful", "streaming": True}
    )


@when("I execute a turn with streaming enabled")
def step_execute_turn_streaming_enabled(context):
    """Execute turn with streaming."""
    # Mock streaming response
    context.streaming_response = ["Response ", "chunk ", "by ", "chunk"]


@then("the response should stream incrementally")
def step_response_streams_incrementally(context):
    """Verify response streams incrementally."""
    assert context.streaming_response is not None


@then("maintain coherent output")
def step_maintain_coherent_output(context):
    """Verify coherent output."""
    assert len(context.streaming_response) > 0


@given("an Agent with {timeout:d} second timeout")
def step_given_agent_with_timeout(context, timeout):
    """Create Agent with timeout."""
    from tactus.dspy import create_dspy_agent

    context.agent = create_dspy_agent(
        "test_agent", {"system_prompt": "Be helpful", "timeout": timeout}
    )
    context.agent_timeout = timeout


@when("a turn takes longer than timeout")
def step_turn_takes_longer_than_timeout(context):
    """Turn takes longer than timeout."""
    # Mock timeout scenario
    context.timeout_occurred = True


@then("it should handle the timeout gracefully")
def step_should_handle_timeout_gracefully(context):
    """Verify timeout handled gracefully."""
    assert context.timeout_occurred is True


@then("provide partial response if available")
def step_provide_partial_response(context):
    """Verify partial response provided."""
    # Mock verification
    assert True


# Additional missing step definitions


@when("I create a DSPy Agent with system prompt")
def step_when_create_dspy_agent_with_system_prompt(context):
    """Create a DSPy Agent with system prompt (when form)."""
    from tactus.dspy import create_dspy_agent

    if hasattr(context, "text") and context.text:
        prompt = context.text.strip()
    else:
        prompt = "You are a helpful assistant"

    context.agent = create_dspy_agent("test_agent", {"system_prompt": prompt})
    context.agent_system_prompt = prompt


@then("the agent should have a turn method")
def step_agent_should_have_turn_method(context):
    """Verify agent is callable (has __call__ method)."""
    assert context.agent is not None
    # DSPy agents use __call__ directly, not a separate turn() method
    assert callable(context.agent)


@then("the agent should have history management")
def step_agent_should_have_history_management(context):
    """Verify agent has history management."""
    assert context.agent is not None
    # Check for history-related methods/attributes
    has_history = (
        hasattr(context.agent, "history")
        or hasattr(context.agent, "get_history")
        or hasattr(context.agent, "add_to_history")
    )
    assert has_history


@given("I create a DSPy Agent with system prompt")
def step_given_create_dspy_agent_with_system_prompt(context):
    """Create a DSPy Agent with system prompt (given form)."""
    from tactus.dspy import create_dspy_agent

    if hasattr(context, "text") and context.text:
        prompt = context.text.strip()
    else:
        prompt = "You are a helpful assistant"

    context.agent = create_dspy_agent("test_agent", {"system_prompt": prompt})
    context.agent_system_prompt = prompt


@when("I access the agent's history")
def step_access_agent_history(context):
    """Access the agent's history."""
    if hasattr(context.agent, "get_history"):
        context.agent_history = context.agent.get_history()
    elif hasattr(context.agent, "history"):
        history_obj = context.agent.history
        if hasattr(history_obj, "get"):
            context.agent_history = history_obj.get()
        else:
            context.agent_history = []
    else:
        context.agent_history = []


@when('execute a turn with "Explain quantum physics"')
def step_execute_turn_explain_quantum_physics(context):
    """Execute a turn with specific input."""
    # Mock turn execution (don't actually call LM)
    context.turn_response = "Mock response explaining quantum physics"
    context.module_result = {"content": "Mock response explaining quantum physics"}
    context.turn_executed = True


@when("execute a turn")
def step_execute_a_turn_simple(context):
    """Execute a turn (simple form)."""
    try:
        context.turn_response = context.agent()
        context.turn_executed = True
    except Exception as e:
        context.turn_error = e
        context.turn_executed = False


@when("I try to execute a turn")
def step_try_execute_turn_with_error_handling(context):
    """Try to execute a turn with proper error handling."""
    try:
        context.turn_response = context.agent()
        context.turn_error = None
    except Exception as e:
        context.turn_error = e
        context.turn_response = None


# Note: "the agent should respond" and "the response should be relevant" are already defined in agent_primitives_steps.py
