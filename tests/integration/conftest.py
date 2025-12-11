"""
Pytest fixtures for integration tests of example procedures.
"""

import pytest
from pathlib import Path
from typing import Dict, Any

from tactus.core.runtime import TactusRuntime
from tactus.core.yaml_parser import ProcedureYAMLParser
from tactus.adapters.memory import MemoryStorage


@pytest.fixture(scope="session")
def examples_dir() -> Path:
    """Get the path to the examples directory."""
    return Path(__file__).parent.parent.parent / "examples"


@pytest.fixture(scope="session")
def example_files(examples_dir: Path):
    """Discover all example procedure files."""
    if not examples_dir.exists():
        pytest.skip(f"Examples directory not found: {examples_dir}")
    files = list(examples_dir.glob("*.tyml"))
    if not files:
        pytest.skip(f"No .tyml files found in {examples_dir}")
    return files


@pytest.fixture
def example_runtime():
    """Fixture providing a configured TactusRuntime for examples.
    
    Uses in-memory storage and no external dependencies (no MCP, no OpenAI).
    Suitable for testing examples that don't require external services.
    """
    return TactusRuntime(
        procedure_id="test-example",
        storage_backend=MemoryStorage(),
        hitl_handler=None,  # No HITL for basic examples
        chat_recorder=None,
        mcp_server=None,  # No MCP tools for basic examples
        openai_api_key=None  # No LLM calls for basic examples
    )


@pytest.fixture
def load_example(examples_dir: Path):
    """Load and parse an example procedure file.
    
    Returns a function that takes an example file path and returns the parsed config.
    """
    def _load(example_file: Path) -> Dict[str, Any]:
        """Load and parse an example file."""
        if not example_file.is_absolute():
            example_file = examples_dir / example_file
        if not example_file.exists():
            raise FileNotFoundError(f"Example file not found: {example_file}")
        
        yaml_content = example_file.read_text()
        return ProcedureYAMLParser.parse(yaml_content)
    
    return _load
