"""
Integration tests for example Tactus procedure files.

These tests automatically discover all .tyml files in the examples/ directory
and verify they execute successfully with proper output validation using Pydantic.
"""

import os
import pytest
from pathlib import Path
from typing import Dict, Any, Type
from pydantic import BaseModel, Field, ValidationError, create_model

from tactus.core.runtime import TactusRuntime
from tactus.core.yaml_parser import ProcedureYAMLParser


def create_output_model_from_schema(output_schema: Dict[str, Any], model_name: str) -> Type[BaseModel]:
    """
    Convert YAML outputs schema to Pydantic model for validation.
    
    This function mirrors the logic from TactusRuntime._create_output_model_from_schema()
    to ensure consistent validation between runtime and tests.
    
    Args:
        output_schema: Dictionary mapping field names to field definitions
        model_name: Name for the generated model class
        
    Returns:
        Pydantic BaseModel class for output validation
    """
    fields = {}
    for field_name, field_def in output_schema.items():
        field_type_str = field_def.get('type', 'string')
        is_required = field_def.get('required', False)

        # Map type strings to Python types
        type_mapping = {
            'string': str,
            'integer': int,
            'number': float,
            'boolean': bool,
            'array': list,
            'object': dict,
        }
        python_type = type_mapping.get(field_type_str, str)

        # Create Field with description if available
        description = field_def.get('description', '')
        if is_required:
            field = Field(..., description=description) if description else Field(...)
        else:
            default = field_def.get('default', None)
            field = Field(default=default, description=description) if description else Field(default=default)

        fields[field_name] = (python_type, field)

    return create_model(model_name, **fields)


def pytest_generate_tests(metafunc):
    """Generate parametrized tests for all example files."""
    if "example_file" in metafunc.fixturenames:
        # Get examples directory
        examples_dir = Path(__file__).parent.parent.parent / "examples"
        if examples_dir.exists():
            example_files = list(examples_dir.glob("*.tyml"))
            metafunc.parametrize("example_file", example_files, ids=lambda p: p.stem)


def requires_llm(example_file: Path) -> bool:
    """Check if an example requires LLM by checking if it calls agent turns."""
    yaml_content = example_file.read_text()
    # Simple heuristic: check if workflow calls .turn()
    return '.turn()' in yaml_content


@pytest.mark.asyncio
async def test_example_executes(
    example_file: Path,
    load_example
):
    """
    Test that example procedure executes successfully and validates output.
    
    This test:
    1. Parses the YAML file
    2. Creates a Pydantic model from the outputs: schema (if present)
    3. Executes the procedure
    4. Validates the output structure matches the schema
    
    LLM-based examples are skipped if OPENAI_API_KEY is not available or if MCP server is not configured.
    """
    # Skip LLM examples if no API key available
    if requires_llm(example_file) and not os.environ.get('OPENAI_API_KEY'):
        pytest.skip(f"Skipping {example_file.name} - requires OPENAI_API_KEY")
    
    # 1. Load and parse YAML
    config = load_example(example_file)
    
    # 2. Create runtime with API key for LLM examples
    from tactus.adapters.memory import MemoryStorage
    api_key = os.environ.get('OPENAI_API_KEY')
    
    example_runtime = TactusRuntime(
        procedure_id=f"test-{example_file.stem}",
        storage_backend=MemoryStorage(),
        hitl_handler=None,
        chat_recorder=None,
        mcp_server=None,  # No MCP server needed - agents work with just API key
        openai_api_key=api_key
    )
    
    # 2. Create Pydantic output model from outputs: schema if present
    OutputModel = None
    if config.get('outputs'):
        OutputModel = create_output_model_from_schema(
            config['outputs'],
            f"{config['name'].replace('_', '').title()}Output"
        )
    
    # 3. Execute procedure
    yaml_content = example_file.read_text()
    result = await example_runtime.execute(yaml_content, context={})
    
    # 4. Validate execution succeeded
    assert result['success'] is True, f"Example {example_file.name} failed to execute: {result.get('error', 'Unknown error')}"
    
    # 5. Validate output structure with Pydantic if schema defined
    if OutputModel and result.get('result'):
        try:
            output_instance = OutputModel(**result['result'])
            # Pydantic will raise ValidationError if schema doesn't match
            # Access validated fields to ensure they're properly typed
            _ = output_instance.model_dump()  # Trigger validation
        except ValidationError as e:
            # Rich error reporting: show which fields failed validation
            error_details = []
            for error in e.errors():
                field = '.'.join(str(loc) for loc in error['loc'])
                error_details.append(
                    f"  {field}: {error['msg']} "
                    f"(input: {error.get('input', 'N/A')}, type: {error.get('type', 'N/A')})"
                )
            
            pytest.fail(
                f"Output validation failed for {example_file.name}:\n"
                f"{len(e.errors())} validation error(s):\n" + "\n".join(error_details)
            )


@pytest.mark.asyncio
async def test_hello_world_outputs_correct_values(
    example_runtime: TactusRuntime,
    examples_dir: Path,
    load_example
):
    """Test hello-world.tyml produces expected output values."""
    example_file = examples_dir / "hello-world.tyml"
    
    if not example_file.exists():
        pytest.skip(f"Example file not found: {example_file}")
    
    config = load_example(example_file)
    OutputModel = create_output_model_from_schema(
        config['outputs'],
        "HelloWorldOutput"
    )
    
    yaml_content = example_file.read_text()
    result = await example_runtime.execute(yaml_content, context={})
    
    assert result['success'] is True
    
    # Validate output with Pydantic model
    output = OutputModel(**result['result'])
    
    # Access validated fields for specific assertions
    assert output.success is True
    assert output.message == "Hello World example completed successfully"
    assert output.count == 5


@pytest.mark.asyncio
async def test_state_management_outputs_correct_count(
    example_runtime: TactusRuntime,
    examples_dir: Path,
    load_example
):
    """Test state-management.tyml produces correct count value."""
    example_file = examples_dir / "state-management.tyml"
    
    if not example_file.exists():
        pytest.skip(f"Example file not found: {example_file}")
    
    config = load_example(example_file)
    OutputModel = create_output_model_from_schema(
        config['outputs'],
        "StateManagementOutput"
    )
    
    yaml_content = example_file.read_text()
    result = await example_runtime.execute(yaml_content, context={})
    
    assert result['success'] is True
    
    output = OutputModel(**result['result'])
    
    assert output.success is True
    assert output.count == 5
    assert "completed successfully" in output.message.lower()


@pytest.mark.asyncio
async def test_with_parameters_uses_defaults(
    example_runtime: TactusRuntime,
    examples_dir: Path,
    load_example
):
    """Test with-parameters.tyml works with default parameter values."""
    example_file = examples_dir / "with-parameters.tyml"
    
    if not example_file.exists():
        pytest.skip(f"Example file not found: {example_file}")
    
    config = load_example(example_file)
    OutputModel = create_output_model_from_schema(
        config['outputs'],
        "WithParametersOutput"
    )
    
    yaml_content = example_file.read_text()
    result = await example_runtime.execute(yaml_content, context={})
    
    assert result['success'] is True
    
    output = OutputModel(**result['result'])
    
    # Check that default parameters were used
    assert "default task" in output.result
    assert "3" in output.result or " 3 " in output.result


@pytest.mark.asyncio
async def test_with_parameters_accepts_overrides(
    example_runtime: TactusRuntime,
    examples_dir: Path,
    load_example
):
    """Test with-parameters.tyml accepts parameter overrides via context."""
    example_file = examples_dir / "with-parameters.tyml"
    
    if not example_file.exists():
        pytest.skip(f"Example file not found: {example_file}")
    
    config = load_example(example_file)
    OutputModel = create_output_model_from_schema(
        config['outputs'],
        "WithParametersOutput"
    )
    
    yaml_content = example_file.read_text()
    # Override parameters via context
    context = {
        'task': 'custom task',
        'count': 7
    }
    result = await example_runtime.execute(yaml_content, context=context)
    
    assert result['success'] is True
    
    output = OutputModel(**result['result'])
    
    # Check that overridden parameters were used
    assert "custom task" in output.result
    assert "7" in output.result or " 7 " in output.result


@pytest.mark.asyncio
async def test_simple_agent_calls_llm_and_done_tool(
    examples_dir: Path,
    load_example
):
    """
    Test simple-agent.tyml makes a real LLM call and the agent calls the done tool.
    
    This test verifies:
    1. The agent actually calls the LLM (not just returns immediately)
    2. The agent calls the 'done' tool as instructed
    3. The greeting output is a non-empty string
    4. The completed flag is True
    """
    import os
    
    # Skip if no API key
    if not os.environ.get('OPENAI_API_KEY'):
        pytest.skip("Skipping simple-agent test - requires OPENAI_API_KEY")
    
    example_file = examples_dir / "simple-agent.tyml"
    
    if not example_file.exists():
        pytest.skip(f"Example file not found: {example_file}")
    
    # Create runtime with API key
    from tactus.adapters.memory import MemoryStorage
    
    api_key = os.environ.get('OPENAI_API_KEY')
    example_runtime = TactusRuntime(
        procedure_id="test-simple-agent-specific",
        storage_backend=MemoryStorage(),
        hitl_handler=None,
        chat_recorder=None,
        mcp_server=None,  # No MCP server needed - agents work with just API key
        openai_api_key=api_key
    )
    
    # Execute the example
    yaml_content = example_file.read_text()
    result = await example_runtime.execute(yaml_content, context={})
    
    # Verify execution succeeded
    assert result['success'] is True, f"Execution failed: {result.get('error')}"
    
    # Verify the agent completed successfully
    assert result['result']['completed'] is True, "Agent did not complete (done tool not called)"
    
    # Verify we got a greeting message
    greeting = result['result']['greeting']
    assert isinstance(greeting, str), f"Greeting should be a string, got {type(greeting)}"
    assert len(greeting) > 0, "Greeting should not be empty"
    
    # Verify the greeting looks like a real greeting (not an error message)
    assert "not complete" not in greeting.lower(), "Greeting indicates agent did not complete properly"
    
    # Verify tools were used (done tool should have been called)
    assert 'tools_used' in result, "Result should include tools_used"
    assert 'done' in result['tools_used'], "Agent should have called the 'done' tool"
