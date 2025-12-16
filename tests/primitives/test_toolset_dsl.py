"""
Tests for toolset DSL integration.
"""

from tactus.core.registry import RegistryBuilder
from tactus.core.dsl_stubs import create_dsl_stubs


def test_toolset_dsl_function_registered():
    """Test that toolset() function is registered in DSL stubs."""
    builder = RegistryBuilder()
    stubs = create_dsl_stubs(builder)

    assert "toolset" in stubs
    assert callable(stubs["toolset"])


def test_toolset_dsl_function_registers_toolset():
    """Test that calling toolset() registers it in the registry."""
    builder = RegistryBuilder()
    stubs = create_dsl_stubs(builder)

    # Call the toolset function
    stubs["toolset"]("test_toolset", {"type": "plugin", "paths": ["./tools"]})

    # Verify it was registered
    assert "test_toolset" in builder.registry.toolsets
    assert builder.registry.toolsets["test_toolset"]["type"] == "plugin"
    assert builder.registry.toolsets["test_toolset"]["paths"] == ["./tools"]


def test_toolset_dsl_function_with_combined_type():
    """Test toolset() with combined type."""
    builder = RegistryBuilder()
    stubs = create_dsl_stubs(builder)

    stubs["toolset"]("combined_toolset", {"type": "combined", "sources": ["toolset1", "toolset2"]})

    assert "combined_toolset" in builder.registry.toolsets
    assert builder.registry.toolsets["combined_toolset"]["type"] == "combined"
    assert builder.registry.toolsets["combined_toolset"]["sources"] == ["toolset1", "toolset2"]


def test_toolset_dsl_function_with_filtered_type():
    """Test toolset() with filtered type."""
    builder = RegistryBuilder()
    stubs = create_dsl_stubs(builder)

    stubs["toolset"](
        "filtered_toolset", {"type": "filtered", "source": "base_toolset", "pattern": "^test_"}
    )

    assert "filtered_toolset" in builder.registry.toolsets
    assert builder.registry.toolsets["filtered_toolset"]["type"] == "filtered"
    assert builder.registry.toolsets["filtered_toolset"]["source"] == "base_toolset"
    assert builder.registry.toolsets["filtered_toolset"]["pattern"] == "^test_"


def test_toolset_dsl_function_with_mcp_type():
    """Test toolset() with mcp type."""
    builder = RegistryBuilder()
    stubs = create_dsl_stubs(builder)

    stubs["toolset"]("mcp_toolset", {"type": "mcp", "server": "plexus"})

    assert "mcp_toolset" in builder.registry.toolsets
    assert builder.registry.toolsets["mcp_toolset"]["type"] == "mcp"
    assert builder.registry.toolsets["mcp_toolset"]["server"] == "plexus"


def test_multiple_toolset_registrations():
    """Test registering multiple toolsets."""
    builder = RegistryBuilder()
    stubs = create_dsl_stubs(builder)

    stubs["toolset"]("toolset1", {"type": "plugin", "paths": ["./tools1"]})
    stubs["toolset"]("toolset2", {"type": "plugin", "paths": ["./tools2"]})
    stubs["toolset"]("toolset3", {"type": "combined", "sources": ["toolset1", "toolset2"]})

    assert len(builder.registry.toolsets) == 3
    assert "toolset1" in builder.registry.toolsets
    assert "toolset2" in builder.registry.toolsets
    assert "toolset3" in builder.registry.toolsets
