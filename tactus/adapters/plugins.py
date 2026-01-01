"""
Local Python Plugin Loader for Tactus.

Provides lightweight tool loading from local Python files without requiring MCP servers.
"""

import logging
import importlib.util
import inspect
import sys
from pathlib import Path
from typing import List, Any, Optional, Callable
from pydantic_ai import Tool
from pydantic_ai.toolsets import FunctionToolset

logger = logging.getLogger(__name__)


class PluginLoader:
    """
    Loader for local Python function tools.

    Scans specified directories and files for Python functions and converts them
    to Pydantic AI Tool instances.

    Convention: Any public function (not starting with _) in the specified paths
    is automatically loaded as a tool. The function's docstring becomes the tool
    description, and type hints are used for parameter validation.
    """

    def __init__(self, tool_primitive: Optional[Any] = None):
        """
        Initialize plugin loader.

        Args:
            tool_primitive: Optional ToolPrimitive for recording tool calls
        """
        self.tool_primitive = tool_primitive
        self.loaded_modules = {}  # Cache loaded modules
        logger.debug("PluginLoader initialized")

    def create_toolset(self, paths: List[str], name: str = "plugin") -> FunctionToolset:
        """
        Create a FunctionToolset from specified paths.

        This is the preferred method for loading plugin tools - it returns a composable
        toolset that can be combined with other toolsets.

        Args:
            paths: List of directory paths or file paths to scan
            name: Name for the toolset (used in logging)

        Returns:
            FunctionToolset instance containing all loaded tools
        """
        # Load all functions from paths
        functions = self._load_all_functions(paths)

        if not functions:
            logger.warning(f"No functions found in paths: {paths}")
            # Return empty toolset
            return FunctionToolset(tools=[])

        # Create toolset
        # Note: FunctionToolset doesn't support process_tool_call parameter
        # Tool call tracking needs to be done at Agent level
        toolset = FunctionToolset(tools=functions)

        logger.info(f"Created FunctionToolset '{name}' with {len(functions)} tool(s)")
        return toolset

    def load_from_paths(self, paths: List[str]) -> List[Tool]:
        """
        Load tools from specified paths (directories or files).

        DEPRECATED: Use create_toolset() instead. This method is kept for backward
        compatibility but will be removed in a future version.

        Args:
            paths: List of directory paths or file paths to scan

        Returns:
            List of pydantic_ai.Tool instances
        """
        all_tools = []

        for path_str in paths:
            path = Path(path_str).resolve()

            if not path.exists():
                logger.warning(f"Tool path does not exist: {path}")
                continue

            if path.is_file():
                # Load tools from single file
                if path.suffix == ".py":
                    tools = self._load_tools_from_file(path)
                    all_tools.extend(tools)
                else:
                    logger.warning(f"Skipping non-Python file: {path}")
            elif path.is_dir():
                # Scan directory for Python files
                tools = self._load_tools_from_directory(path)
                all_tools.extend(tools)
            else:
                logger.warning(f"Path is neither file nor directory: {path}")

        logger.info(f"Loaded {len(all_tools)} tools from {len(paths)} path(s)")
        return all_tools

    def _load_all_functions(self, paths: List[str]) -> List[Callable]:
        """
        Load all functions from specified paths.

        Args:
            paths: List of directory paths or file paths to scan

        Returns:
            List of callable functions (not wrapped in Tool)
        """
        all_functions = []

        for path_str in paths:
            path = Path(path_str).resolve()

            if not path.exists():
                logger.warning(f"Tool path does not exist: {path}")
                continue

            if path.is_file():
                if path.suffix == ".py":
                    functions = self._load_functions_from_file(path)
                    all_functions.extend(functions)
                else:
                    logger.warning(f"Skipping non-Python file: {path}")
            elif path.is_dir():
                functions = self._load_functions_from_directory(path)
                all_functions.extend(functions)
            else:
                logger.warning(f"Path is neither file nor directory: {path}")

        logger.debug(f"Loaded {len(all_functions)} function(s) from {len(paths)} path(s)")
        return all_functions

    def _load_functions_from_directory(self, directory: Path) -> List[Callable]:
        """
        Scan directory for Python files and load functions.

        Args:
            directory: Directory path to scan

        Returns:
            List of callable functions
        """
        functions = []

        for py_file in directory.glob("*.py"):
            if py_file.name.startswith("_"):
                continue

            file_functions = self._load_functions_from_file(py_file)
            functions.extend(file_functions)

        return functions

    def _load_functions_from_file(self, file_path: Path) -> List[Callable]:
        """
        Load functions from a single Python file.

        Args:
            file_path: Path to Python file

        Returns:
            List of callable functions
        """
        functions = []

        try:
            # Create module name from file path
            module_name = f"tactus_plugin_{file_path.stem}_{id(file_path)}"

            # Load module dynamically
            spec = importlib.util.spec_from_file_location(module_name, file_path)
            if spec is None or spec.loader is None:
                logger.error(f"Could not load spec for {file_path}")
                return functions

            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)

            # Cache the module
            self.loaded_modules[str(file_path)] = module

            logger.debug(f"Loaded module from {file_path}")

            # Find all public functions in the module
            for name, obj in inspect.getmembers(module):
                if self._is_valid_tool_function(name, obj, module):
                    functions.append(obj)
                    logger.debug(f"Found function '{name}' in {file_path.name}")

        except Exception as e:
            logger.error(f"Failed to load functions from {file_path}: {e}", exc_info=True)

        return functions

    def _create_trace_callback(self, toolset_name: str):
        """
        Create a tool call tracing callback for the toolset.

        Args:
            toolset_name: Name of the toolset

        Returns:
            Async callback function for process_tool_call
        """

        async def trace_tool_call(ctx, next_call, tool_name, tool_args):
            """Middleware to record tool calls in Tactus ToolPrimitive."""
            logger.debug(
                f"Toolset '{toolset_name}' calling tool '{tool_name}' with args: {tool_args}"
            )

            try:
                result = await next_call(tool_name, tool_args)

                # Record in ToolPrimitive if available
                if self.tool_primitive:
                    result_str = str(result) if not isinstance(result, str) else result
                    self.tool_primitive.record_call(tool_name, tool_args, result_str)

                logger.debug(f"Tool '{tool_name}' completed successfully")
                return result
            except Exception as e:
                logger.error(f"Tool '{tool_name}' failed: {e}", exc_info=True)
                # Still record the failed call
                if self.tool_primitive:
                    error_msg = f"Error: {str(e)}"
                    self.tool_primitive.record_call(tool_name, tool_args, error_msg)
                raise

        return trace_tool_call

    def _load_tools_from_directory(self, directory: Path) -> List[Tool]:
        """
        Recursively scan directory for Python files and load tools.

        Args:
            directory: Directory path to scan

        Returns:
            List of Tool instances
        """
        tools = []

        # Find all .py files (non-recursive for now)
        for py_file in directory.glob("*.py"):
            if py_file.name.startswith("_"):
                # Skip private modules (e.g., __init__.py, __pycache__)
                continue

            file_tools = self._load_tools_from_file(py_file)
            tools.extend(file_tools)

        return tools

    def _load_tools_from_file(self, file_path: Path) -> List[Tool]:
        """
        Load tools from a single Python file.

        Args:
            file_path: Path to Python file

        Returns:
            List of Tool instances
        """
        tools = []

        try:
            # Create module name from file path
            module_name = f"tactus_plugin_{file_path.stem}_{id(file_path)}"

            # Load module dynamically
            spec = importlib.util.spec_from_file_location(module_name, file_path)
            if spec is None or spec.loader is None:
                logger.error(f"Could not load spec for {file_path}")
                return tools

            module = importlib.util.module_from_spec(spec)

            # Add to sys.modules so imports work
            sys.modules[module_name] = module

            # Execute module
            spec.loader.exec_module(module)

            # Cache the module
            self.loaded_modules[str(file_path)] = module

            logger.debug(f"Loaded module from {file_path}")

            # Find all public functions in the module
            for name, obj in inspect.getmembers(module):
                if self._is_valid_tool_function(name, obj, module):
                    tool = self._create_tool_from_function(obj, name)
                    if tool:
                        tools.append(tool)
                        logger.info(f"Loaded tool '{name}' from {file_path.name}")

        except Exception as e:
            logger.error(f"Failed to load tools from {file_path}: {e}", exc_info=True)

        return tools

    def _is_valid_tool_function(self, name: str, obj: Any, module: Any) -> bool:
        """
        Check if an object is a valid tool function.

        Args:
            name: Object name
            obj: Object to check
            module: Module the object belongs to

        Returns:
            True if object is a valid tool function
        """
        # Must be a function
        if not inspect.isfunction(obj):
            return False

        # Must be public (not start with _)
        if name.startswith("_"):
            return False

        # Must be defined in this module (not imported)
        if obj.__module__ != module.__name__:
            return False

        return True

    def _create_tool_from_function(self, func: Callable, name: str) -> Optional[Tool]:
        """
        Create a Pydantic AI Tool from a Python function.

        Args:
            func: Python function to wrap
            name: Tool name

        Returns:
            Tool instance or None if creation fails
        """
        try:
            # Get function signature and docstring
            sig = inspect.signature(func)
            doc = inspect.getdoc(func) or f"Tool: {name}"

            # Check if function is async
            is_async = inspect.iscoroutinefunction(func)

            # Create wrapper that records tool calls
            if is_async:

                async def tool_wrapper(*args, **kwargs):
                    """Async wrapper for tool function."""
                    try:
                        result = await func(*args, **kwargs)

                        # Record tool call if tool_primitive is available
                        if self.tool_primitive:
                            self.tool_primitive.record_call(name, kwargs, str(result))

                        return result
                    except Exception as e:
                        logger.error(f"Tool '{name}' execution failed: {e}", exc_info=True)
                        error_msg = f"Error executing tool '{name}': {str(e)}"

                        # Record failed call
                        if self.tool_primitive:
                            self.tool_primitive.record_call(name, kwargs, error_msg)

                        raise

            else:

                def tool_wrapper(*args, **kwargs):
                    """Sync wrapper for tool function."""
                    try:
                        result = func(*args, **kwargs)

                        # Record tool call if tool_primitive is available
                        if self.tool_primitive:
                            self.tool_primitive.record_call(name, kwargs, str(result))

                        return result
                    except Exception as e:
                        logger.error(f"Tool '{name}' execution failed: {e}", exc_info=True)
                        error_msg = f"Error executing tool '{name}': {str(e)}"

                        # Record failed call
                        if self.tool_primitive:
                            self.tool_primitive.record_call(name, kwargs, error_msg)

                        raise

            # Copy signature and docstring to wrapper
            tool_wrapper.__signature__ = sig
            tool_wrapper.__doc__ = doc
            tool_wrapper.__name__ = name
            tool_wrapper.__annotations__ = func.__annotations__

            # Create Pydantic AI Tool
            tool = Tool(tool_wrapper, name=name, description=doc)

            return tool

        except Exception as e:
            logger.error(f"Failed to create tool from function '{name}': {e}", exc_info=True)
            return None
