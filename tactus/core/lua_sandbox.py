"""
Lua Sandbox - Safe, restricted Lua execution environment.

Provides a sandboxed Lua runtime with:
- Data format libraries restricted to working directory (Csv, Tsv, Parquet, Hdf5, Excel)
- File and Json primitives injected separately by runtime
- require() available but restricted to loading .tac files from working directory only
- No dangerous operations (debug, io, loadfile, dofile removed)
- Only whitelisted primitives available
- Resource limits on CPU time and memory
"""

import logging
import os
from typing import Any, Optional

try:
    import lupa
    from lupa import LuaRuntime

    LUPA_AVAILABLE = True
except ImportError:
    LUPA_AVAILABLE = False
    LuaRuntime = None

logger = logging.getLogger(__name__)


class LuaSandboxError(Exception):
    """Raised when Lua sandbox setup or execution fails."""

    pass


class LuaSandbox:
    """Sandboxed Lua execution environment for procedure workflows."""

    def __init__(
        self,
        execution_context: Optional[Any] = None,
        strict_determinism: bool = False,
        base_path: Optional[str] = None,
    ):
        """
        Initialize the Lua sandbox.

        Args:
            execution_context: Optional ExecutionContext for checkpoint scope tracking
            strict_determinism: If True, raise errors instead of warnings for non-deterministic ops
            base_path: Optional base path for file operations and require(). Defaults to cwd.
        """
        if not LUPA_AVAILABLE:
            raise LuaSandboxError("lupa library not available. Install with: pip install lupa")

        # Store context for safe libraries
        self.execution_context = execution_context
        self.strict_determinism = strict_determinism

        # Fix base_path at initialization time to prevent security boundary expansion
        # This ensures file I/O libraries and require() always use the same base path,
        # even if the working directory changes later
        self.base_path = base_path or os.getcwd()

        # Create Lua runtime with safety restrictions
        self.lua = LuaRuntime(
            unpack_returned_tuples=True,
            attribute_filter=self._attribute_filter,
        )

        # Remove dangerous modules
        self._remove_dangerous_modules()

        # Configure safe require/package
        self._setup_safe_require()

        # Setup safe globals
        self._setup_safe_globals()

        logger.debug("Lua sandbox initialized successfully")

    def _attribute_filter(self, obj: Any, attr_name: str, is_setting: bool) -> str:
        """
        Filter attribute access to prevent dangerous operations.

        This is called by lupa for all attribute access from Lua code.
        """
        # Block access to private/protected attributes
        if attr_name.startswith("_"):
            raise AttributeError(f"Access to private attribute '{attr_name}' is not allowed")

        # Block access to certain dangerous methods
        blocked_attributes = {
            "__import__",
            "__loader__",
            "__spec__",
            "__builtins__",
            "eval",
            "exec",
            "compile",
            "open",
            "__subclasses__",
        }

        if attr_name in blocked_attributes:
            raise AttributeError(f"Access to '{attr_name}' is not allowed in sandbox")

        return attr_name

    def _remove_dangerous_modules(self) -> None:
        """Remove dangerous Lua standard library modules."""
        # Remove modules that provide file system or system access
        # Note: 'package' and 'require' are kept but restricted in _setup_safe_require()
        dangerous_modules = [
            "io",  # File I/O
            "os",  # Operating system operations
            "dofile",  # Load and execute files
            "loadfile",  # Load files
            "load",  # Load code
        ]

        lua_globals = self.lua.globals()

        for module in dangerous_modules:
            if module in lua_globals:
                lua_globals[module] = None
                logger.debug(f"Removed dangerous module/function: {module}")

        # Whitelist only safe debug functions for source location tracking
        # Keep debug.getinfo but remove dangerous debug functions
        if "debug" in lua_globals:
            self.lua.execute(
                """
                if debug then
                    local safe_debug = {
                        getinfo = debug.getinfo
                    }
                    debug = safe_debug
                end
                """
            )
            logger.debug("Replaced debug module with safe_debug (only getinfo allowed)")

    def _setup_safe_require(self) -> None:
        """Configure require/package to search user's project and stdlib.

        This allows using Lua's require() mechanism while restricting module
        loading to:
        1. User's project directory (base_path) - for local modules
        2. Tactus stdlib directory - for standard library modules

        Example:
            require("helpers/math")       -- loads from base_path/helpers/math.tac
            require("tactus.tools.done")  -- loads from stdlib/tac/tactus/tools/done.tac
        """
        import tactus

        # Get stdlib path from installed package location
        package_root = os.path.dirname(tactus.__file__)
        stdlib_tac_path = os.path.join(package_root, "stdlib", "tac")

        # Build search paths:
        # 1. User's project directory (existing behavior)
        # 2. Tactus stdlib .tac files
        # Both single-file modules (?.tac) and directory modules (?/init.tac) are supported
        user_module_path = os.path.join(self.base_path, "?.tac")
        user_init_path = os.path.join(self.base_path, "?", "init.tac")
        stdlib_module_path = os.path.join(stdlib_tac_path, "?.tac")
        stdlib_init_path = os.path.join(stdlib_tac_path, "?", "init.tac")

        # Normalize backslashes for cross-platform compatibility
        raw_paths = [
            user_module_path,
            user_init_path,
            stdlib_module_path,
            stdlib_init_path,
        ]
        normalized_paths = [path.replace("\\", "/") for path in raw_paths]

        # Join with Lua's path separator (semicolon)
        safe_path = ";".join(normalized_paths)

        lua_globals = self.lua.globals()
        package = lua_globals["package"]

        if package:
            # Set restricted search paths
            package["path"] = safe_path

            # Disable C module loading entirely
            package["cpath"] = ""

            # Clear preloaded modules that might provide dangerous access
            if package["preload"]:
                self.lua.execute("for k in pairs(package.preload) do package.preload[k] = nil end")

            # Add Python stdlib loader
            self._setup_python_stdlib_loader()

            logger.debug("Configured safe require with paths: %s", safe_path)
        else:
            logger.warning("package module not available - require will not work")

    def _setup_python_stdlib_loader(self) -> None:
        """Add custom loader for Python stdlib modules."""
        from tactus.stdlib.loader import StdlibModuleLoader

        # Create loader instance
        self._stdlib_loader = StdlibModuleLoader(self, self.base_path)
        loader_func = self._stdlib_loader.create_loader_function()

        # Inject loader function into Lua
        self.lua.globals()["_tactus_python_loader"] = loader_func

        # Add to package.loaders (Lua 5.1) or package.searchers (Lua 5.2+)
        # Lupa uses LuaJIT which follows Lua 5.1 conventions
        self.lua.execute(
            """
            -- Add Python stdlib loader to package.loaders
            -- Insert after the preload loader but before path loader
            local loaders = package.loaders or package.searchers
            if loaders then
                -- Create wrapper that returns a loader function (Lua convention)
                local function python_searcher(modname)
                    local result = _tactus_python_loader(modname)
                    if result then
                        -- Return a loader function that returns the module
                        return function() return result end
                    end
                    return nil
                end

                -- Insert at position 2 (after preload, before path)
                table.insert(loaders, 2, python_searcher)
            end
            """
        )

        logger.debug("Python stdlib loader installed")

    def _setup_safe_globals(self) -> None:
        """Setup safe global functions and utilities."""
        # Keep safe standard library functions
        # (These are already available by default, just documenting them)
        safe_functions = {
            # Math
            "math",  # Math library (will be replaced with safe version if context available)
            "tonumber",  # Convert to number
            "tostring",  # Convert to string
            # String operations
            "string",  # String library
            # Table operations
            "table",  # Table library
            "pairs",  # Iterate over tables
            "ipairs",  # Iterate over arrays
            "next",  # Next element in table
            # Type checking
            "type",  # Get type of value
            "assert",  # Assertions
            "error",  # Raise error
            "pcall",  # Protected call (try/catch)
            # Other safe operations
            "select",  # Select arguments
            "unpack",  # Unpack table (Lua 5.1)
        }

        # Just log what's available - no need to explicitly set
        logger.debug("Safe Lua functions available: %s", ", ".join(safe_functions))

        # Replace math and os libraries with safe versions if context available
        if self.execution_context is not None:
            from tactus.utils.safe_libraries import (
                create_safe_math_library,
                create_safe_os_library,
            )

            def get_context():
                return self.execution_context

            safe_math_dict = create_safe_math_library(get_context, self.strict_determinism)
            safe_os_dict = create_safe_os_library(get_context, self.strict_determinism)

            safe_math_table = self._dict_to_lua_table(safe_math_dict)
            safe_os_table = self._dict_to_lua_table(safe_os_dict)

            self.lua.globals()["math"] = safe_math_table
            self.lua.globals()["os"] = safe_os_table

            logger.debug("Installed safe math and os libraries with determinism checking")
            return  # Skip default os.date setup below

        # Add safe subset of os module (only date function for timestamps)
        # This is a fallback when no execution context is available (testing/REPL)
        from datetime import datetime

        def safe_date(format_str=None):
            """Safe implementation of os.date() for timestamp generation."""
            now = datetime.utcnow()
            if format_str is None:
                # Return default format like Lua's os.date()
                return now.strftime("%a %b %d %H:%M:%S %Y")
            elif format_str == "%Y-%m-%dT%H:%M:%SZ":
                # ISO 8601 format
                return now.strftime("%Y-%m-%dT%H:%M:%SZ")
            else:
                # Support Python strftime formats
                try:
                    return now.strftime(format_str)
                except Exception:  # noqa: E722
                    return now.strftime("%a %b %d %H:%M:%S %Y")

        # Create safe os table with only date function
        safe_os = self.lua.table(date=safe_date)
        self.lua.globals()["os"] = safe_os
        logger.debug("Added safe os.date() function")

    def setup_assignment_interception(self, callback: Any) -> None:
        """
        Setup assignment interception on global scope to capture variable definitions.

        This allows capturing assignments like: greeter = Agent {...}
        The callback will be invoked with (name, value) whenever a new global is assigned.

        Args:
            callback: Python function or Lua function to call on assignment
                     Should accept (name: str, value: Any) -> None

        Example usage:
            sandbox.setup_assignment_interception(lambda name, val: print(f"{name} = {val}"))
            sandbox.execute("greeter = Agent {...}")  # Triggers callback
        """
        # Store callback in Lua globals so metatable can access it
        self.lua.globals()["_tactus_intercept_callback"] = callback

        # Set metatable directly on _G (don't replace _G with proxy table)
        lua_code = """
        local mt = {
            __newindex = function(t, key, value)
                -- Call the Python callback if it exists
                if _tactus_intercept_callback then
                    _tactus_intercept_callback(key, value)
                end
                -- Actually set the value
                rawset(t, key, value)
            end
        }
        setmetatable(_G, mt)
        """

        try:
            self.lua.execute(lua_code)
            logger.debug("Assignment interception enabled with metatable on _G")
        except Exception as exception:
            logger.error(
                "Failed to setup assignment interception: %s",
                exception,
                exc_info=True,
            )
            raise LuaSandboxError(f"Could not setup assignment interception: {exception}")

    def set_execution_context(self, context: Any) -> None:
        """
        Set or update execution context and refresh safe libraries.

        Args:
            context: ExecutionContext instance
        """
        self.execution_context = context
        # Re-setup safe globals with context
        self._setup_safe_globals()
        logger.debug("ExecutionContext attached to LuaSandbox")

    def inject_primitive(self, name: str, primitive_obj: Any) -> None:
        """
        Inject a Python primitive object into Lua globals.

        Args:
            name: Name of the primitive in Lua (e.g., "State", "Worker")
            primitive_obj: Python object to expose to Lua
        """
        self.lua.globals()[name] = primitive_obj
        logger.debug("Injected primitive '%s' into Lua sandbox", name)

    def set_global(self, name: str, value: Any) -> None:
        """
        Set a global variable in Lua.

        Args:
            name: Name of the global variable
            value: Value to set (can be Python object, dict, etc.)
        """
        self.lua.globals()[name] = self._convert_python_value_to_lua(value)
        logger.debug("Set global '%s' in Lua sandbox", name)

    def _convert_python_value_to_lua(self, value: Any) -> Any:
        """Convert Python values to Lua-friendly values."""
        if isinstance(value, dict):
            return self._dict_to_lua_table(value)
        return value

    def _dict_to_lua_table(self, python_dict: dict) -> Any:
        """Convert Python dict to Lua table recursively."""
        lua_table = self.lua.table()
        for key, value in python_dict.items():
            lua_table[key] = self._convert_python_value_to_lua(value)
        return lua_table

    def execute(self, lua_code: str) -> Any:
        """
        Execute Lua code in the sandbox.

        Args:
            lua_code: Lua code string to execute

        Returns:
            Result of the Lua code execution

        Raises:
            LuaSandboxError: If execution fails
        """
        try:
            logger.debug("Executing Lua code (%s bytes)", len(lua_code))
            result = self.lua.execute(lua_code)
            logger.debug("Lua execution completed successfully")
            return result

        except lupa.LuaError as exception:
            # Lua runtime error
            error_message = str(exception)
            logger.error("Lua execution error: %s", error_message)
            raise LuaSandboxError(f"Lua runtime error: {error_message}")

        except Exception as exception:
            # Other Python exceptions
            logger.error("Sandbox execution error: %s", exception)
            raise LuaSandboxError(f"Sandbox error: {exception}")

    def eval(self, lua_expression: str) -> Any:
        """
        Evaluate a Lua expression and return the result.

        Args:
            lua_expression: Lua expression to evaluate

        Returns:
            Result of the expression

        Raises:
            LuaSandboxError: If evaluation fails
        """
        try:
            result = self.lua.eval(lua_expression)
            return result

        except lupa.LuaError as exception:
            error_message = str(exception)
            logger.error("Lua eval error: %s", error_message)
            raise LuaSandboxError(f"Lua eval error: {error_message}")

    def get_global(self, name: str) -> Any:
        """Get a value from Lua global scope."""
        return self.lua.globals()[name]

    def create_lua_table(self, python_dict: Optional[dict[str, Any]] = None) -> Any:
        """
        Create a Lua table from a Python dictionary.

        Args:
            python_dict: Python dictionary to convert (or None for empty table)

        Returns:
            Lua table object
        """
        if python_dict is None:
            # Create empty Lua table
            return self.lua.table()

        # Create and populate Lua table
        lua_table = self.lua.table()
        for key, value in python_dict.items():
            lua_table[key] = self._convert_python_value_to_lua(value)

        return lua_table

    def lua_table_to_dict(self, lua_table: Any) -> dict[str, Any]:
        """
        Convert a Lua table to a Python dictionary.

        Args:
            lua_table: Lua table object

        Returns:
            Python dictionary
        """
        result = {}

        try:
            # Use Lua's pairs() to iterate
            for key, value in self.lua.globals().pairs(lua_table):
                # Convert Lua values to Python types
                if isinstance(value, self.lua.table_from):
                    # Recursively convert nested tables
                    result[key] = self.lua_table_to_dict(value)
                else:
                    result[key] = value

        except Exception as exception:
            logger.warning("Error converting Lua table to dict: %s", exception)
            # Fallback: try direct iteration
            try:
                for key in lua_table:
                    result[key] = lua_table[key]
            except Exception:  # noqa: E722
                pass

        return result
