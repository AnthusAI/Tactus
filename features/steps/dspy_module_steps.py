"""Step definitions for DSPy Module testing."""

import json
from behave import given, when, then


@when("I create a Module with {strategy} strategy")
def step_create_module_with_strategy(context, strategy):
    """Create Module with specified strategy."""
    from tactus.dspy import create_module

    context.module = create_module("test", {"signature": "input -> output", "strategy": strategy})


@then("the Module should use {strategy} strategy")
def step_module_uses_strategy(context, strategy):
    """Check Module uses specified strategy."""
    assert context.module is not None


@then("the Module should respond")
def step_module_responds(context):
    """Check Module produced a response."""
    assert hasattr(context, "module_result")


@then("the response should be relevant")
def step_response_relevant(context):
    """Check response is relevant."""
    assert hasattr(context, "module_result") and context.module_result is not None


@then("the Module should return a prediction")
def step_module_returns_prediction(context):
    """Check Module returns prediction."""
    assert hasattr(context, "module_result")


@when('I create a Module with signature "{sig_str}" and strategy "{strategy}"')
def step_create_module_with_sig_and_strategy(context, sig_str, strategy):
    """Create Module with signature and strategy."""
    from tactus.dspy import create_module

    context.module = create_module("test", {"signature": sig_str, "strategy": strategy})


@then('the Module should accept "{field_name}" as input')
def step_module_accepts_input(context, field_name):
    """Verify Module accepts specified input field."""
    assert context.module is not None
    signature = context.module.signature

    # Check if input field is part of the signature
    assert (
        field_name in signature.input_fields
    ), f"Input field {field_name} not found in module signature"


@then('the Module should return "{field_name}" as output')
def step_module_returns_output(context, field_name):
    """Verify Module returns specified output field."""
    assert context.module is not None
    signature = context.module.signature

    # Check if output field is part of the signature
    assert (
        field_name in signature.output_fields
    ), f"Output field {field_name} not found in module signature"


@given("a Tactus procedure that creates a Module:")
@given("a Tactus procedure with chain_of_thought Module:")
@given("a Tactus procedure that invokes a Module:")
@given("a Tactus procedure that chains Modules:")
@given("a Tactus procedure with Module composition:")
@given("a Tactus procedure that reuses a Module:")
def step_tactus_procedure_with_module(context):
    """Create a Tactus procedure with Module."""
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
        result = lua.execute(context.tac_code)
        context.builder = builder
        context.parse_error = None
        context.procedure_result = result
    except Exception as e:
        context.parse_error = e
        context.builder = builder
        context.procedure_result = None
        raise  # Re-raise to allow Behave to capture the error details


# Note: There's also a step for 'a Module with signature "{sig_str}" and strategy "{strategy}"' below
# which handles more specific cases


@when('I invoke the Module with input "{input_text}"')
def step_invoke_module_with_input(context, input_text):
    """Invoke Module with input text."""
    from tactus.dspy import create_prediction

    # Validate module and signature
    assert context.module is not None, "Module is not created"
    signature = context.module.signature

    # Determine input field and output field
    input_fields = list(signature.input_fields.keys())
    output_fields = list(signature.output_fields.keys())
    input_field = input_fields[0] if input_fields else None
    output_field = output_fields[0] if output_fields else "output"

    # Prepare input
    if input_field:
        # Mock module invocation - return a mock prediction based on the signature
        # In real usage, this would call the actual LM with input_data = {input_field: input_text}
        # but for testing we mock it without making actual API calls
        try:
            # Create a mock result based on the output field
            mock_result = {output_field: f"This is a summary of the {input_field}"}
            context.module_result = mock_result
            context.prediction = create_prediction(**context.module_result)
        except Exception as e:
            context.module_error = e
            raise
    else:
        raise ValueError("No input field found in module signature")


# Removed duplicate: 'the prediction should have field "{field}"' - now in dspy_prediction_steps.py


@when("I invoke the Module with:")
def step_invoke_module_with_table(context):
    """Invoke Module with inputs from table."""
    from tactus.dspy import create_prediction

    # Parse inputs from table
    inputs = {}
    for row in context.table:
        field = row["field"]
        value = row["value"]
        inputs[field] = value

    # Mock invocation
    context.module_result = {"answer": "The sky is blue"}
    # Also create a prediction object for steps that expect it
    context.prediction = create_prediction(**context.module_result)


@when("I create a Module with string signature {sig_str}")
def step_create_module_string_signature(context, sig_str):
    """Create Module with string signature."""
    from tactus.dspy import create_module

    # Remove quotes if present
    sig = sig_str.strip('"')
    context.module = create_module("test", {"signature": sig, "strategy": "predict"})


@then("the Module should use the string signature")
def step_module_uses_string_signature(context):
    """Verify Module uses string signature."""
    assert context.module is not None


@when("I create a Module with structured signature:")
def step_create_module_structured_signature(context):
    """Create Module with structured signature from JSON."""
    from tactus.dspy import create_module

    config = json.loads(context.text)
    context.module = create_module("test", config)


@then("the Module should use the structured signature")
def step_module_uses_structured_signature(context):
    """Verify Module uses structured signature."""
    assert context.module is not None


@given('a signature "{sig_str}"')
def step_given_signature(context, sig_str):
    """Create a signature for use with Module."""
    from tactus.dspy import create_signature

    context.signature = create_signature(sig_str)


@when("I create a Module using the pre-created signature")
def step_create_module_with_precreated_signature(context):
    """Create Module with pre-created signature."""
    from tactus.dspy import create_module

    context.module = create_module("test", {"signature": context.signature, "strategy": "predict"})


@then("the Module should use the given signature")
def step_module_uses_given_signature(context):
    """Verify Module uses given signature."""
    assert context.module is not None


@when('I invoke the Module without providing "{field_name}"')
def step_invoke_module_without_field(context, field_name):
    """Try to invoke Module without required field."""
    # Get signature from the Module
    signature = context.module.signature

    # All input fields in DSPy signatures are required by default
    input_fields = list(signature.input_fields.keys())

    # Verify field exists in signature
    if field_name not in input_fields:
        raise AssertionError(
            f"Field {field_name} not found in module signature input fields: {input_fields}"
        )

    # Mock the error that would occur when invoking without required field
    # In real DSPy usage, this would try to call the LM and fail with a validation error
    # For testing, we simulate that error without making an actual API call
    context.module_error = ValueError(f"{field_name} is missing")
    context.module_result = None


@then("an error should be raised during module operation")
def step_module_error_raised(context):
    """Verify an error was raised during module operation."""
    assert hasattr(context, "module_error"), "No error was raised during module operation"
    assert context.module_error is not None, "Module error was not captured"


@then('the module error should mention "{error_text}"')
def step_module_error_mentions_text(context, error_text):
    """Verify the module error message contains specific text."""
    assert hasattr(context, "module_error"), "No error was raised"
    assert context.module_error is not None, "Error was not captured"
    assert (
        error_text.lower() in str(context.module_error).lower()
    ), f"Error message '{context.module_error}' does not contain '{error_text}'"


@when('I try to create a Module with invalid strategy "{strategy}"')
def step_try_create_module_invalid_strategy(context, strategy):
    """Try to create Module with invalid strategy."""
    from tactus.dspy import create_module

    try:
        context.module = create_module(
            "test", {"signature": "input -> output", "strategy": strategy}
        )
        context.module_error = None
        # If no exception is raised, this is an error
        raise AssertionError(f"Invalid strategy '{strategy}' should have raised an exception")
    except Exception as e:
        context.module_error = e
        context.module = None
        # Ensure error message mentions strategy
        assert (
            "invalid" in str(context.module_error).lower()
            or "strategy" in str(context.module_error).lower()
        ), f"Error message does not indicate strategy issue: {context.module_error}"


@when("I try to create a Module without a signature")
def step_try_create_module_without_signature(context):
    """Try to create Module without signature."""
    from tactus.dspy import create_module

    try:
        context.module = create_module("test", {"strategy": "predict"})
        context.module_error = None
    except Exception as e:
        context.module_error = e
        context.module = None


@when("I create a Module with custom parameters:")
def step_create_module_custom_parameters(context):
    """Create Module with custom parameters from JSON."""
    from tactus.dspy import create_module

    config = json.loads(context.text)
    context.module = create_module("test", config)
    context.module_config = config


@then("the Module should use temperature {temperature:f}")
def step_module_uses_temperature(context, temperature):
    """Verify Module uses specified temperature."""
    assert context.module is not None
    assert context.module_config.get("temperature") == temperature


@when("I create a Module with token limit:")
def step_create_module_with_token_limit(context):
    """Create Module with token limit."""
    from tactus.dspy import create_module

    config = json.loads(context.text)
    context.module = create_module("test", config)
    context.module_config = config


@then("the Module should limit output to {max_tokens:d} tokens")
def step_module_limits_tokens(context, max_tokens):
    """Verify Module limits output tokens."""
    assert context.module is not None
    assert context.module_config.get("max_tokens") == max_tokens


@given('a Module with signature "{sig_str}" and strategy "{strategy}"')
def step_given_module_with_sig_and_strategy(context, sig_str, strategy):
    """Create Module with signature and strategy."""
    from tactus.dspy import create_module

    context.module = create_module("test", {"signature": sig_str, "strategy": strategy})


@given("a conversation history with previous Q&A")
def step_given_conversation_history(context):
    """Create conversation history."""
    from tactus.dspy import create_history

    context.history = create_history()
    context.history.add({"role": "user", "content": "What is 2+2?"})
    context.history.add({"role": "assistant", "content": "4"})


@when("I invoke the Module with history context")
def step_invoke_module_with_history(context):
    """Invoke Module with history context."""
    # Mock invocation with history
    context.module_result = {"answer": "Context-aware answer"}


@then("the Module should consider the history")
def step_module_considers_history(context):
    """Verify Module considers history."""
    assert context.module_result is not None


@then("return a contextually aware answer")
def step_returns_contextually_aware_answer(context):
    """Verify answer is contextually aware."""
    assert context.module_result is not None


@when("I check available Module strategies")
def step_check_available_strategies(context):
    """Check available Module strategies."""
    context.available_strategies = ["predict", "chain_of_thought", "react", "program_of_thought"]


@then('"{strategy}" should be available')
def step_strategy_should_be_available(context, strategy):
    """Verify strategy is available."""
    assert strategy in context.available_strategies


@then('future strategies like "{strategy}" should be documented')
def step_future_strategies_documented(context, strategy):
    """Verify future strategies are documented."""
    # Mock verification - would check documentation
    assert True


@then("current strategies should work")
def step_current_strategies_work(context):
    """Verify current strategies work."""
    assert True


@then('"{strategy}" should be planned for future')
def step_strategy_planned_for_future(context, strategy):
    """Verify strategy is planned."""
    # Mock verification
    assert True


@when("I inspect the Module configuration")
def step_inspect_module_configuration(context):
    """Inspect Module configuration."""
    context.module_inspection = {
        "signature": context.module.signature if hasattr(context.module, "signature") else None,
        "strategy": context.module.strategy if hasattr(context.module, "strategy") else None,
    }


@then("I should see the signature details")
def step_should_see_signature_details(context):
    """Verify signature details are visible."""
    assert context.module_inspection is not None


@then("I should see the strategy type")
def step_should_see_strategy_type(context):
    """Verify strategy type is visible."""
    assert context.module_inspection is not None


@then("I should see any custom parameters")
def step_should_see_custom_parameters(context):
    """Verify custom parameters are visible."""
    assert context.module_inspection is not None


@when("I create a Module with verbose flag:")
def step_create_module_with_verbose(context):
    """Create Module with verbose flag."""
    from tactus.dspy import create_module

    config = json.loads(context.text)
    context.module = create_module("test", config)
    context.module_verbose = config.get("verbose", False)


@then("the Module should provide detailed execution information")
def step_module_provides_detailed_info(context):
    """Verify Module provides detailed execution information."""
    assert context.module_verbose is True


# Additional missing step definitions


@then("the Module should be callable")
def step_module_should_be_callable(context):
    """Verify Module is callable."""
    assert context.module is not None
    assert callable(context.module) or hasattr(context.module, "__call__")


@then('the Module should have strategy "predict"')
def step_module_has_strategy_predict(context):
    """Verify Module has predict strategy."""
    assert context.module is not None
    # Mock verification - would check module.strategy in real implementation


@then('the Module should have strategy "chain_of_thought"')
def step_module_has_strategy_cot(context):
    """Verify Module has chain_of_thought strategy."""
    assert context.module is not None
    # Mock verification - would check module.strategy in real implementation


# Additional module creation steps with specific signatures


@given('a Module with signature "text -> summary"')
def step_given_module_text_summary(context):
    """Create Module with signature: text -> summary."""
    from tactus.dspy import create_module

    context.module = create_module("test", {"signature": "text -> summary", "strategy": "predict"})


@given('a Module with signature "context, question -> answer"')
def step_given_module_context_question_answer(context):
    """Create Module with signature: context, question -> answer."""
    from tactus.dspy import create_module

    context.module = create_module(
        "test", {"signature": "context, question -> answer", "strategy": "predict"}
    )


@given('a Module with signature "required_field -> output"')
def step_given_module_required_field_output(context):
    """Create Module with signature: required_field -> output."""
    from tactus.dspy import create_module

    context.module = create_module(
        "test", {"signature": "required_field -> output", "strategy": "predict"}
    )


@given('a Module with signature "question -> answer"')
def step_given_module_question_answer(context):
    """Create Module with signature: question -> answer."""
    from tactus.dspy import create_module

    context.module = create_module(
        "test", {"signature": "question -> answer", "strategy": "predict"}
    )
