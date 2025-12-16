"""
Toolset Primitive - Manages and composes tool collections in Tactus.

Provides first-class support for Pydantic AI's composable toolset architecture.
"""

import logging
from typing import Any, Dict, Callable
from pydantic_ai.toolsets import AbstractToolset, CombinedToolset, FilteredToolset

logger = logging.getLogger(__name__)


class ToolsetPrimitive:
    """
    Toolset primitive for managing and composing tool collections.

    Exposes Pydantic AI's toolset composition features to the Lua DSL.

    Example Lua usage:
        toolset("financial", {type = "plugin", paths = {"./tools/financial"}})

        local ts = Toolset.get("financial")
        local combined = Toolset.combine(ts1, ts2)
        local filtered = Toolset.filter(ts, function(name) return name:match("^web_") end)
    """

    def __init__(self, runtime):
        """
        Initialize toolset primitive.

        Args:
            runtime: TactusRuntime instance for resolving toolset references
        """
        self.runtime = runtime
        self.definitions = {}  # name -> toolset config (from DSL)
        logger.debug("ToolsetPrimitive initialized")

    def define(self, name: str, config: Dict[str, Any]) -> None:
        """
        Register a toolset definition from the DSL.

        This is called when the Lua DSL uses: toolset("name", {...})

        Args:
            name: Toolset name
            config: Configuration dict with type and type-specific params

        Example config:
            {
                "type": "plugin",
                "paths": ["./tools/financial"]
            }
            {
                "type": "mcp",
                "server": "plexus"
            }
            {
                "type": "combined",
                "sources": ["financial", "plexus"]
            }
        """
        self.definitions[name] = config
        logger.info(f"Defined toolset '{name}' of type '{config.get('type')}'")

    def get(self, name: str) -> AbstractToolset:
        """
        Get a toolset by name.

        Resolves the toolset from runtime's registered toolsets or creates it
        from a DSL definition.

        Args:
            name: Toolset name

        Returns:
            AbstractToolset instance

        Raises:
            ValueError: If toolset not found
        """
        # Try to resolve from runtime first (config-defined toolsets)
        toolset = self.runtime.resolve_toolset(name)
        if toolset:
            return toolset

        # Try DSL definitions
        if name in self.definitions:
            return self._create_toolset_from_definition(name, self.definitions[name])

        raise ValueError(f"Toolset '{name}' not found (not in config or DSL)")

    def combine(self, *toolsets) -> CombinedToolset:
        """
        Combine multiple toolsets into one.

        Args:
            *toolsets: Variable number of AbstractToolset instances

        Returns:
            CombinedToolset containing all input toolsets
        """
        toolset_list = list(toolsets)
        logger.debug(f"Combining {len(toolset_list)} toolsets")
        return CombinedToolset(toolset_list)

    def filter(self, toolset: AbstractToolset, predicate: Callable[[str], bool]) -> FilteredToolset:
        """
        Filter tools in a toolset based on a predicate function.

        Args:
            toolset: Toolset to filter
            predicate: Function that takes tool name and returns bool

        Returns:
            FilteredToolset with only matching tools

        Example:
            filtered = Toolset.filter(ts, function(name)
                return name:match("^web_")
            end)
        """

        # Wrap Lua function for Pydantic AI's filter API
        # Pydantic AI's filtered() expects: lambda ctx, tool: bool
        def pydantic_filter(ctx, tool):
            # Call Lua predicate with just the tool name
            return predicate(tool.name)

        logger.debug("Creating filtered toolset")
        return toolset.filtered(pydantic_filter)

    def _create_toolset_from_definition(self, name: str, config: Dict[str, Any]) -> AbstractToolset:
        """
        Create a toolset from a DSL definition.

        Args:
            name: Toolset name
            config: Toolset configuration

        Returns:
            Created toolset instance

        Raises:
            ValueError: If toolset type is unknown
        """
        toolset_type = config.get("type")

        if toolset_type == "plugin":
            return self._create_plugin_toolset(name, config)
        elif toolset_type == "mcp":
            return self._create_mcp_toolset_reference(name, config)
        elif toolset_type == "combined":
            return self._create_combined_toolset(name, config)
        elif toolset_type == "filtered":
            return self._create_filtered_toolset(name, config)
        else:
            raise ValueError(f"Unknown toolset type: {toolset_type}")

    def _create_plugin_toolset(self, name: str, config: Dict[str, Any]) -> AbstractToolset:
        """Create a plugin toolset from paths."""
        from tactus.adapters.plugins import PluginLoader

        paths = config.get("paths", [])
        if not paths:
            raise ValueError(f"Plugin toolset '{name}' must specify 'paths'")

        loader = PluginLoader(tool_primitive=self.runtime.tool_primitive)
        toolset = loader.create_toolset(paths, name=name)
        return toolset

    def _create_mcp_toolset_reference(self, name: str, config: Dict[str, Any]) -> AbstractToolset:
        """Get reference to an MCP toolset."""
        server_name = config.get("server")
        if not server_name:
            raise ValueError(f"MCP toolset '{name}' must specify 'server' name")

        # MCP toolsets are created during runtime initialization
        # Look them up from runtime's MCP manager
        if not hasattr(self.runtime, "mcp_manager") or not self.runtime.mcp_manager:
            raise ValueError(f"MCP server '{server_name}' not configured")

        # Find the toolset by server name (MCP toolsets are prefixed)
        for toolset in self.runtime.mcp_manager.get_toolsets():
            # TODO: Add a way to identify toolsets by server name
            # For now, just return the first one
            # This needs proper implementation in MCPServerManager
            logger.warning("MCP toolset reference not fully implemented - using first available")
            return toolset

        raise ValueError(f"MCP server toolset '{server_name}' not found")

    def _create_combined_toolset(self, name: str, config: Dict[str, Any]) -> CombinedToolset:
        """Create a combined toolset from sources."""
        sources = config.get("sources", [])
        if not sources:
            raise ValueError(f"Combined toolset '{name}' must specify 'sources'")

        # Resolve each source toolset
        resolved_toolsets = []
        for source_name in sources:
            toolset = self.get(source_name)
            resolved_toolsets.append(toolset)

        return CombinedToolset(resolved_toolsets)

    def _create_filtered_toolset(self, name: str, config: Dict[str, Any]) -> FilteredToolset:
        """Create a filtered toolset."""
        source = config.get("source")
        filter_pattern = config.get("filter")

        if not source:
            raise ValueError(f"Filtered toolset '{name}' must specify 'source'")
        if not filter_pattern:
            raise ValueError(f"Filtered toolset '{name}' must specify 'filter' pattern")

        # Get source toolset
        source_toolset = self.get(source)

        # Create filter function (simple regex match for now)
        import re

        pattern = re.compile(filter_pattern)

        def filter_func(ctx, tool):
            return pattern.match(tool.name) is not None

        return source_toolset.filtered(filter_func)

    def __repr__(self) -> str:
        return f"ToolsetPrimitive({len(self.definitions)} definitions)"
