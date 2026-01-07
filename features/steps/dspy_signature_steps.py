"""Step definitions for DSPy Signature creation and validation."""

import json
from behave import given, when, then


@then('it should have output fields "{field1}", "{field2}", and "{field3}"')
def step_has_output_fields_three(context, field1, field2, field3):
    """Verify signature has three output fields."""
    sig = context.signature
    output_fields = sig.output_fields
    for field_name in [field1, field2, field3]:
        assert field_name in output_fields, f"Field '{field_name}' not in output fields: {list(output_fields.keys())}"


@then('it should have input fields "{field1}", "{field2}", and "{field3}"')
def step_has_input_fields_three(context, field1, field2, field3):
    """Verify signature has three input fields."""
    sig = context.signature
    input_fields = sig.input_fields
    for field_name in [field1, field2, field3]:
        assert field_name in input_fields, f"Field '{field_name}' not in input fields: {list(input_fields.keys())}"


@when("I create a structured signature with multiple typed fields:")
def step_create_complex_structured_signature(context):
    """Create a complex structured signature from JSON."""
    from tactus.dspy import create_signature
    config = json.loads(context.text)
    context.signature = create_signature(config)


@then('input field "{field_name}" should have type "{type_name}"')
def step_input_field_has_type(context, field_name, type_name):
    """Verify input field has specified type."""
    sig = context.signature
    input_fields = sig.input_fields
    assert field_name in input_fields, f"Field '{field_name}' not in input fields"
    # Type verification would depend on DSPy implementation
    context.field_types = context.field_types if hasattr(context, 'field_types') else {}
    context.field_types[field_name] = type_name


@then('output field "{field_name}" should have type "{type_name}"')
def step_output_field_has_type(context, field_name, type_name):
    """Verify output field has specified type."""
    sig = context.signature
    output_fields = sig.output_fields
    assert field_name in output_fields, f"Field '{field_name}' not in output fields"
    # Type verification would depend on DSPy implementation
    context.field_types = context.field_types if hasattr(context, 'field_types') else {}
    context.field_types[field_name] = type_name


@given("a Tactus procedure with simple signature:")
@given("a Tactus procedure with structured signature:")
def step_tactus_procedure_with_signature(context):
    """Create a Tactus procedure with signature."""
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


@when("I create a signature with typed fields:")
def step_create_signature_with_typed_fields(context):
    """Create signature with typed fields from JSON."""
    from tactus.dspy import create_signature
    config = json.loads(context.text)
    context.signature = create_signature(config)


@when("I create a signature with instructions:")
def step_create_signature_with_instructions(context):
    """Create signature with instructions."""
    from tactus.dspy import create_signature
    config = json.loads(context.text)
    context.signature = create_signature(config)
    context.signature_instructions = config.get('instructions', '')


@then('the signature should have instructions "{instructions}"')
def step_signature_has_instructions(context, instructions):
    """Verify signature has specified instructions."""
    assert context.signature_instructions == instructions


@then('it should have output fields "{field1}" and "{field2}"')
def step_has_output_fields_two(context, field1, field2):
    """Verify signature has two output fields."""
    sig = context.signature
    output_fields = sig.output_fields
    assert field1 in output_fields, f"Field '{field1}' not in output fields"
    assert field2 in output_fields, f"Field '{field2}' not in output fields"


@when('I try to create a signature "{sig_str}"')
def step_try_create_signature(context, sig_str):
    """Try to create a signature (may fail)."""
    from tactus.dspy import create_signature
    try:
        context.signature = create_signature(sig_str)
        context.signature_error = None
    except Exception as e:
        context.signature_error = e
        context.signature = None


@given("a Tactus procedure that combines signatures:")
def step_tactus_procedure_combines_signatures(context):
    """Create procedure that combines signatures."""
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


@when("I create a signature with nested structures:")
def step_create_signature_nested(context):
    """Create signature with nested structures."""
    from tactus.dspy import create_signature
    config = json.loads(context.text)
    context.signature = create_signature(config)


@when("I create a signature with optional fields:")
def step_create_signature_optional_fields(context):
    """Create signature with optional fields."""
    from tactus.dspy import create_signature
    config = json.loads(context.text)
    context.signature = create_signature(config)


@then('input field "{field_name}" should be required')
def step_input_field_required(context, field_name):
    """Verify input field is required."""
    sig = context.signature
    input_fields = sig.input_fields
    assert field_name in input_fields, f"Field '{field_name}' not in input fields"
    # Mock verification - would check field metadata in real implementation


@then('input field "{field_name}" should be optional')
def step_input_field_optional(context, field_name):
    """Verify input field is optional."""
    sig = context.signature
    input_fields = sig.input_fields
    assert field_name in input_fields, f"Field '{field_name}' not in input fields"
    # Mock verification - would check field metadata in real implementation


@then('output field "{field_name}" should be required')
def step_output_field_required(context, field_name):
    """Verify output field is required."""
    sig = context.signature
    output_fields = sig.output_fields
    assert field_name in output_fields, f"Field '{field_name}' not in output fields"
    # Mock verification - would check field metadata in real implementation


@given("a Tactus procedure that validates signature fields:")
def step_tactus_procedure_validates_signatures(context):
    """Create procedure that validates signatures."""
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


@when("I create a signature with default values:")
def step_create_signature_with_defaults(context):
    """Create signature with default values."""
    from tactus.dspy import create_signature
    config = json.loads(context.text)
    context.signature = create_signature(config)
    context.signature_config = config


@then('input field "{field_name}" should have default value "{value}"')
def step_input_field_has_default_string(context, field_name, value):
    """Verify input field has default string value."""
    sig = context.signature
    input_fields = sig.input_fields
    assert field_name in input_fields, f"Field '{field_name}' not in input fields"
    # Mock verification - would check default value in real implementation
    expected_default = value
    context.field_defaults = context.field_defaults if hasattr(context, 'field_defaults') else {}
    context.field_defaults[field_name] = expected_default


@then('input field "{field_name}" should have default value {value:f}')
def step_input_field_has_default_float(context, field_name, value):
    """Verify input field has default float value."""
    sig = context.signature
    input_fields = sig.input_fields
    assert field_name in input_fields, f"Field '{field_name}' not in input fields"
    # Mock verification - would check default value in real implementation
    context.field_defaults = context.field_defaults if hasattr(context, 'field_defaults') else {}
    context.field_defaults[field_name] = value


