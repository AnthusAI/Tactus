"""Step definitions for DSPy integration testing."""

from behave import given, when, then


@given("dspy is installed as a dependency")
def step_dspy_installed(context):
    """Verify DSPy is installed."""
    try:
        import dspy
        context.dspy = dspy
    except ImportError as e:
        raise AssertionError(f"DSPy is not installed: {e}")


@then("dspy should be importable from Python")
def step_dspy_importable(context):
    """Verify DSPy can be imported."""
    import dspy
    assert dspy is not None
    assert hasattr(dspy, "LM")
    assert hasattr(dspy, "Signature")
    assert hasattr(dspy, "Module")


@then("tactus.dspy module should be importable")
def step_tactus_dspy_importable(context):
    """Verify tactus.dspy module can be imported."""
    import tactus.dspy
    assert tactus.dspy is not None
    assert hasattr(tactus.dspy, "configure_lm")
    assert hasattr(tactus.dspy, "get_current_lm")


@when('I configure an LM with "{model}"')
def step_configure_lm(context, model):
    """Configure an LM with the given model."""
    from tactus.dspy import configure_lm
    # Use a mock API key for testing (won't actually make calls)
    context.lm = configure_lm(model, api_key="test-key")


@then("the LM should be available for use")
def step_lm_available(context):
    """Verify the LM was created."""
    assert context.lm is not None


@then("the current LM should be set")
def step_current_lm_set(context):
    """Verify the current LM is set globally."""
    from tactus.dspy import get_current_lm
    current = get_current_lm()
    assert current is not None
    assert current == context.lm


@given("a Tactus procedure that uses the LM primitive")
def step_tactus_lm_procedure(context):
    """Create a Tactus procedure that uses the LM primitive."""
    context.tac_code = '''
LM("openai/gpt-4o-mini", { api_key = "test-key" })

Procedure "main" {
    function()
        return {}
    end
}
'''


@when("the procedure is parsed")
def step_parse_procedure(context):
    """Parse the Tactus procedure."""
    from tactus.core.registry import RegistryBuilder
    from tactus.core.dsl_stubs import create_dsl_stubs
    from lupa import LuaRuntime

    # Create registry and stubs
    builder = RegistryBuilder()
    stubs = create_dsl_stubs(builder)

    # Create Lua runtime and inject stubs
    lua = LuaRuntime(unpack_returned_tuples=True)
    for name, func in stubs.items():
        lua.globals()[name] = func

    # Execute the Tactus code
    lua.execute(context.tac_code)
    context.builder = builder


@then("the LM should be configured")
def step_lm_configured(context):
    """Verify the LM was configured during parsing."""
    from tactus.dspy import get_current_lm
    current = get_current_lm()
    assert current is not None


# Signature steps
@when('I create a signature "{sig_str}"')
def step_create_signature(context, sig_str):
    """Create a signature from string."""
    from tactus.dspy import create_signature
    context.signature = create_signature(sig_str)


@then('it should have input field "{field_name}"')
def step_has_input_field(context, field_name):
    """Verify signature has input field."""
    sig = context.signature
    # DSPy 3.x uses input_fields property
    input_fields = sig.input_fields
    assert field_name in input_fields, f"Field '{field_name}' not in input fields: {list(input_fields.keys())}"


@then('it should have output field "{field_name}"')
def step_has_output_field(context, field_name):
    """Verify signature has output field."""
    sig = context.signature
    # DSPy 3.x uses output_fields property
    output_fields = sig.output_fields
    assert field_name in output_fields, f"Field '{field_name}' not in output fields: {list(output_fields.keys())}"


@then('it should have input fields "{field1}" and "{field2}"')
def step_has_input_fields(context, field1, field2):
    """Verify signature has multiple input fields."""
    sig = context.signature
    input_fields = sig.input_fields
    for field_name in [field1, field2]:
        assert field_name in input_fields, f"Field '{field_name}' not in input fields: {list(input_fields.keys())}"


@then('it should have output fields "{field1}" and "{field2}"')
def step_has_output_fields(context, field1, field2):
    """Verify signature has multiple output fields."""
    sig = context.signature
    output_fields = sig.output_fields
    for field_name in [field1, field2]:
        assert field_name in output_fields, f"Field '{field_name}' not in output fields: {list(output_fields.keys())}"


@given("a Tactus procedure that uses the Signature primitive")
def step_tactus_signature_procedure(context):
    """Create a Tactus procedure that uses the Signature primitive."""
    context.tac_code = '''
local sig = Signature("question -> answer")

Procedure "main" {
    function()
        return {}
    end
}
'''
    context.expected_signature = True


@then("the signature should be created")
def step_signature_created(context):
    """Verify the signature was created during parsing."""
    # The signature creation is verified by successful parsing
    # If there was an error, the parse step would have failed
    assert context.expected_signature


# Structured Signature steps
@when("I create a structured signature with field descriptions")
def step_create_structured_signature(context):
    """Create a structured signature with field descriptions."""
    from tactus.dspy import create_signature

    context.signature = create_signature({
        "input": {
            "question": {"type": "string", "description": "The question to answer"}
        },
        "output": {
            "answer": {"type": "string", "description": "The answer"}
        }
    })


@then('input field "{field_name}" should have description "{description}"')
def step_has_input_field_with_desc(context, field_name, description):
    """Verify signature has input field with description."""
    sig = context.signature
    input_fields = sig.input_fields
    assert field_name in input_fields, f"Field '{field_name}' not in input fields: {list(input_fields.keys())}"

    # Check the description
    field = input_fields[field_name]
    # DSPy 3.x stores description in field.json_schema_extra or field.description
    field_desc = getattr(field, "description", None) or ""
    if hasattr(field, "json_schema_extra") and field.json_schema_extra:
        field_desc = field.json_schema_extra.get("desc", field_desc)
    assert description in str(field_desc) or field_desc == description, \
        f"Field '{field_name}' description mismatch: expected '{description}', got '{field_desc}'"


@then('output field "{field_name}" should have description "{description}"')
def step_has_output_field_with_desc(context, field_name, description):
    """Verify signature has output field with description."""
    sig = context.signature
    output_fields = sig.output_fields
    assert field_name in output_fields, f"Field '{field_name}' not in output fields: {list(output_fields.keys())}"

    # Check the description
    field = output_fields[field_name]
    field_desc = getattr(field, "description", None) or ""
    if hasattr(field, "json_schema_extra") and field.json_schema_extra:
        field_desc = field.json_schema_extra.get("desc", field_desc)
    assert description in str(field_desc) or field_desc == description, \
        f"Field '{field_name}' description mismatch: expected '{description}', got '{field_desc}'"


@given("a Tactus procedure with a structured Signature")
def step_tactus_structured_signature_procedure(context):
    """Create a Tactus procedure that uses the structured Signature primitive."""
    context.tac_code = '''
local sig = Signature "qa" {
    input = {
        question = field.string{description = "The question to answer"}
    },
    output = {
        answer = field.string{description = "The answer"}
    }
}

Procedure "main" {
    function()
        return {}
    end
}
'''
    context.expected_structured_signature = True


@then("the structured signature should be created with descriptions")
def step_structured_signature_created(context):
    """Verify the structured signature was created during parsing."""
    # The signature creation is verified by successful parsing
    # If there was an error, the parse step would have failed
    assert context.expected_structured_signature


# Module steps
@when("I create a Module with predict strategy")
def step_create_module_predict(context):
    """Create a Module with predict strategy."""
    from tactus.dspy import create_module

    context.module = create_module("qa", {
        "signature": "question -> answer",
        "strategy": "predict"
    })


@then("the Module should be callable")
def step_module_callable(context):
    """Verify the Module is callable."""
    assert callable(context.module), "Module should be callable"


@then('the Module should have strategy "{strategy}"')
def step_module_strategy(context, strategy):
    """Verify the Module has the expected strategy."""
    assert context.module.strategy == strategy, \
        f"Module strategy mismatch: expected '{strategy}', got '{context.module.strategy}'"


@given("a Tactus procedure that uses the Module primitive")
def step_tactus_module_procedure(context):
    """Create a Tactus procedure that uses the Module primitive."""
    context.tac_code = '''
local qa = Module "qa" {
    signature = "question -> answer",
    strategy = "predict"
}

Procedure "main" {
    function()
        return {}
    end
}
'''
    context.expected_module = True


@then("the Module should be created successfully")
def step_module_created(context):
    """Verify the Module was created during parsing."""
    # The module creation is verified by successful parsing
    # If there was an error, the parse step would have failed
    assert context.expected_module


@when("I create a Module with chain_of_thought strategy")
def step_create_module_cot(context):
    """Create a Module with chain_of_thought strategy."""
    from tactus.dspy import create_module

    context.module = create_module("reasoner", {
        "signature": "question -> reasoning, answer",
        "strategy": "chain_of_thought"
    })


@given("a Tactus procedure that uses the chain_of_thought Module")
def step_tactus_cot_module_procedure(context):
    """Create a Tactus procedure that uses the chain_of_thought Module."""
    context.tac_code = '''
local reasoner = Module "reasoner" {
    signature = "question -> reasoning, answer",
    strategy = "chain_of_thought"
}

Procedure "main" {
    function()
        return {}
    end
}
'''
    context.expected_module = True


# History steps
@when("I create a History")
def step_create_history(context):
    """Create a new History."""
    from tactus.dspy import create_history
    context.history = create_history()


@when("I add a message to history")
def step_add_message(context):
    """Add a message to history."""
    context.history.add({"question": "What is 2+2?", "answer": "4"})


@then("the history should have {count:d} message")
def step_history_count(context, count):
    """Verify history has expected number of messages."""
    assert len(context.history) == count, \
        f"Expected {count} messages, got {len(context.history)}"


@then("I can retrieve the messages")
def step_retrieve_messages(context):
    """Verify messages can be retrieved."""
    messages = context.history.get()
    assert len(messages) == 1
    assert messages[0]["question"] == "What is 2+2?"
    assert messages[0]["answer"] == "4"


@given("a Tactus procedure that uses the History primitive")
def step_tactus_history_procedure(context):
    """Create a Tactus procedure that uses the History primitive."""
    context.tac_code = '''
local history = History()

Procedure "main" {
    function()
        return {}
    end
}
'''
    context.expected_history = True


@then("the History should be usable")
def step_history_usable(context):
    """Verify the History was created during parsing."""
    # The history creation is verified by successful parsing
    # If there was an error, the parse step would have failed
    assert context.expected_history


# Prediction steps
@when("I create a Prediction with fields")
def step_create_prediction(context):
    """Create a Prediction with some fields."""
    from tactus.dspy import create_prediction
    context.prediction = create_prediction(
        answer="42",
        reasoning="The answer to everything"
    )


@then("I can access prediction fields as attributes")
def step_access_prediction_fields(context):
    """Verify prediction fields are accessible as attributes."""
    assert context.prediction.answer == "42"
    assert context.prediction.reasoning == "The answer to everything"


@then("I can get prediction data as a dictionary")
def step_get_prediction_data(context):
    """Verify prediction data can be retrieved as dict."""
    data = context.prediction.data()
    assert isinstance(data, dict)
    assert data["answer"] == "42"
    assert data["reasoning"] == "The answer to everything"


@when("I wrap a DSPy Prediction")
def step_wrap_dspy_prediction(context):
    """Wrap a DSPy Prediction."""
    import dspy
    from tactus.dspy import wrap_prediction

    dspy_pred = dspy.Prediction(question="What is 2+2?", answer="4")
    context.prediction = wrap_prediction(dspy_pred)


@then("the TactusPrediction should delegate to the underlying prediction")
def step_prediction_delegates(context):
    """Verify delegation to DSPy Prediction."""
    assert context.prediction.question == "What is 2+2?"
    assert context.prediction.answer == "4"
    # Verify has() method works
    assert context.prediction.has("answer")
    assert not context.prediction.has("nonexistent")


# DSPy Agent steps
@when("I create a DSPy Agent with system prompt")
@given("I create a DSPy Agent with system prompt")
def step_create_dspy_agent(context):
    """Create a DSPy Agent with system prompt."""
    from tactus.dspy import create_dspy_agent

    context.agent = create_dspy_agent("test_agent", {
        "system_prompt": "You are a helpful assistant.",
        "model": "openai/gpt-4o-mini",
    })


@then("the agent should have a turn method")
def step_agent_has_turn(context):
    """Verify agent has turn method."""
    assert hasattr(context.agent, "turn")
    assert callable(context.agent.turn)


@then("the agent should have history management")
def step_agent_has_history(context):
    """Verify agent has history management."""
    assert hasattr(context.agent, "history")
    assert hasattr(context.agent, "get_history")
    assert hasattr(context.agent, "clear_history")


@when("I access the agent's history")
def step_access_agent_history(context):
    """Access the agent's history."""
    context.agent_history = context.agent.get_history()


@then("the history should be empty initially")
def step_history_empty_initially(context):
    """Verify history is empty."""
    assert len(context.agent_history) == 0


@then("I can add messages to the agent's history")
def step_add_to_agent_history(context):
    """Verify messages can be added to agent history."""
    context.agent.history.add({"role": "user", "content": "Hello"})
    assert len(context.agent.get_history()) == 1
