"""
Python stdlib module loader for Tactus.

Provides a mechanism to load Python modules from tactus/stdlib/
via Lua's require() function. Only modules with the "tactus." prefix
can be loaded, ensuring user code cannot import arbitrary Python modules.
"""

import importlib.util
import inspect
import logging
import sys
from pathlib import Path
from typing import Any, Callable, Dict

logger = logging.getLogger(__name__)


class StdlibModuleLoader:
    """
    Loads Python modules from tactus/stdlib/ for Lua require().

    Security: Only loads from the stdlib path, never user directories.
    """

    def __init__(self, lua_sandbox, base_path: str):
        """
        Initialize the stdlib loader.

        Args:
            lua_sandbox: LuaSandbox instance for table creation
            base_path: Base path for file operations (passed to modules)
        """
        self.lua_sandbox = lua_sandbox
        self.base_path = base_path
        self.stdlib_path = self._get_stdlib_path()
        self.loaded_modules: Dict[str, Any] = {}

    def _get_stdlib_path(self) -> Path:
        """Get the stdlib directory path."""
        import tactus

        package_root = Path(tactus.__file__).parent
        return package_root / "stdlib"

    def create_loader_function(self) -> Callable:
        """
        Create the loader function to inject into Lua's package.loaders.

        Returns:
            Python function that Lua can call as a module loader
        """

        def python_stdlib_loader(module_name: str):
            """
            Lua module loader for Python stdlib modules.

            Args:
                module_name: Module path like "tactus.io.json"

            Returns:
                Lua table with module functions, or None if not found
            """
            # Only handle tactus.* modules (stdlib)
            if not module_name.startswith("tactus."):
                return None

            # Convert module path to file path
            # "tactus.io.json" -> "io/json.py"
            relative_path = module_name[7:].replace(".", "/")  # Remove "tactus." prefix
            python_path = self.stdlib_path / f"{relative_path}.py"

            # Security: Verify path is within stdlib
            try:
                python_path = python_path.resolve()
                python_path.relative_to(self.stdlib_path.resolve())
            except ValueError:
                logger.warning(f"Path traversal attempt blocked: {module_name}")
                return None

            # Check if Python module exists
            if not python_path.exists():
                return None

            # Load and wrap the Python module
            try:
                return self._load_python_module(module_name, python_path)
            except Exception as e:
                logger.error(f"Failed to load stdlib module {module_name}: {e}")
                # Re-raise as a string for Lua error handling
                raise RuntimeError(f"Failed to load module '{module_name}': {e}")

        return python_stdlib_loader

    def _load_python_module(self, module_name: str, path: Path) -> Any:
        """
        Load a Python module and convert to Lua table.

        Args:
            module_name: Full module name (e.g., "tactus.io.json")
            path: Path to Python file

        Returns:
            Lua table with module exports
        """
        # Check cache
        if module_name in self.loaded_modules:
            return self.loaded_modules[module_name]

        # Create unique module name for Python's import system
        internal_name = f"tactus_stdlib_{module_name.replace('.', '_')}"

        # Load module dynamically
        spec = importlib.util.spec_from_file_location(internal_name, path)
        if spec is None or spec.loader is None:
            raise ImportError(f"Could not load spec for {path}")

        module = importlib.util.module_from_spec(spec)
        sys.modules[internal_name] = module

        # Inject context before executing module
        module.__tactus_context__ = TactusStdlibContext(
            base_path=self.base_path, lua_sandbox=self.lua_sandbox
        )

        spec.loader.exec_module(module)

        # Get exports
        exports = self._get_module_exports(module)

        # Convert to Lua table
        lua_table = self._create_lua_module(exports)

        # Cache
        self.loaded_modules[module_name] = lua_table

        logger.debug(f"Loaded stdlib Python module: {module_name}")
        return lua_table

    def _get_module_exports(self, module) -> Dict[str, Callable]:
        """
        Get exportable functions from a module.

        Args:
            module: Loaded Python module

        Returns:
            Dict of function name -> function
        """
        exports = {}

        # Check for explicit exports list
        explicit_exports = getattr(module, "__tactus_exports__", None)

        for name, obj in inspect.getmembers(module):
            # Skip private
            if name.startswith("_"):
                continue

            # Skip non-functions
            if not callable(obj):
                continue

            # Skip if not in explicit exports (when defined)
            if explicit_exports is not None and name not in explicit_exports:
                continue

            # Skip imports from other modules
            if hasattr(obj, "__module__") and obj.__module__ != module.__name__:
                continue

            exports[name] = obj

        return exports

    def _create_lua_module(self, exports: Dict[str, Callable]) -> Any:
        """
        Create a Lua table from Python exports.

        Args:
            exports: Dict of function name -> function

        Returns:
            Lua table
        """
        lua_table = self.lua_sandbox.lua.table()

        for name, func in exports.items():
            # Wrap function to handle type conversion
            wrapped = self._wrap_function(func, name)
            lua_table[name] = wrapped

        return lua_table

    def _wrap_function(self, func: Callable, name: str) -> Callable:
        """
        Wrap a Python function for Lua interop.

        Handles:
        - Lua table -> Python dict conversion
        - Python dict -> Lua table conversion
        - Exception propagation
        """

        def wrapper(*args):
            try:
                # Convert Lua tables to Python dicts
                python_args = [self._lua_to_python(arg) for arg in args]

                # Call function
                result = func(*python_args)

                # Convert result to Lua
                return self._python_to_lua(result)

            except Exception as e:
                logger.error(f"Error in stdlib function {name}: {e}")
                raise

        return wrapper

    def _lua_to_python(self, value: Any) -> Any:
        """Convert Lua value to Python."""
        # Use existing conversion from safe_file_library
        from tactus.utils.safe_file_library import _lua_to_python

        return _lua_to_python(value)

    def _python_to_lua(self, value: Any) -> Any:
        """Convert Python value to Lua table recursively."""
        if value is None:
            return None
        if isinstance(value, (str, int, float, bool)):
            return value
        if isinstance(value, dict):
            # Convert dict to Lua table recursively
            lua_table = self.lua_sandbox.lua.table()
            for k, v in value.items():
                lua_table[k] = self._python_to_lua(v)
            return lua_table
        if isinstance(value, (list, tuple)):
            # Convert to Lua array (1-indexed)
            lua_table = self.lua_sandbox.lua.table()
            for i, item in enumerate(value, start=1):
                lua_table[i] = self._python_to_lua(item)
            return lua_table
        # Fallback
        return value


class TactusStdlibContext:
    """
    Context object passed to stdlib Python modules.

    Provides access to sandbox resources in a controlled way.
    """

    def __init__(self, base_path: str, lua_sandbox):
        self.base_path = base_path
        self._lua_sandbox = lua_sandbox
        self._path_validator = None

    @property
    def path_validator(self):
        """Lazy-create path validator."""
        if self._path_validator is None:
            from tactus.utils.safe_file_library import PathValidator

            self._path_validator = PathValidator(self.base_path)
        return self._path_validator

    def validate_path(self, filepath: str) -> str:
        """Validate and resolve a file path."""
        return self.path_validator.validate(filepath)
