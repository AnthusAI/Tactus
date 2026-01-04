"""
Lua Sandbox - Safe, restricted Lua execution environment.

Provides a sandboxed Lua runtime with:
- Data format libraries restricted to working directory (Csv, Tsv, Parquet, Hdf5, Excel)
- File and Json primitives injected separately by runtime
- No dangerous operations (debug, package, require removed)
- Only whitelisted primitives available
- Resource limits on CPU time and memory
"""

import logging
import os
from typing import Dict, Any, Optional

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

    def __init__(self, execution_context: Optional[Any] = None, strict_determinism: bool = False):
        """
        Initialize the Lua sandbox.

        Args:
            execution_context: Optional ExecutionContext for checkpoint scope tracking
            strict_determinism: If True, raise errors instead of warnings for non-deterministic ops
        """
        if not LUPA_AVAILABLE:
            raise LuaSandboxError("lupa library not available. Install with: pip install lupa")

        # Store context for safe libraries
        self.execution_context = execution_context
        self.strict_determinism = strict_determinism

        # Fix base_path at initialization time to prevent security boundary expansion
        # This ensures file I/O libraries always use the same base path, even if
        # the working directory changes later (e.g., when set_execution_context is called)
        self.base_path = os.getcwd()

        # Create Lua runtime with safety restrictions
        self.lua = LuaRuntime(unpack_returned_tuples=True, attribute_filter=self._attribute_filter)

        # Remove dangerous modules
        self._remove_dangerous_modules()

        # Setup safe globals
        self._setup_safe_globals()

        logger.info("Lua sandbox initialized successfully")

    def _attribute_filter(self, obj, attr_name, is_setting):
        """
        Filter attribute access to prevent dangerous operations.

        This is called by lupa for all attribute access from Lua code.
        """
        # Block access to private/protected attributes
        if attr_name.startswith("_"):
            raise AttributeError(f"Access to private attribute '{attr_name}' is not allowed")

        # Block access to certain dangerous methods
        blocked_methods = {
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

        if attr_name in blocked_methods:
            raise AttributeError(f"Access to '{attr_name}' is not allowed in sandbox")

        return attr_name

    def _remove_dangerous_modules(self):
        """Remove dangerous Lua standard library modules."""
        # Remove modules that provide file system or system access
        dangerous_modules = [
            "io",  # File I/O
            "os",  # Operating system operations
            "package",  # Module loading
            "dofile",  # Load and execute files
            "loadfile",  # Load files
            "load",  # Load code
            "require",  # Require modules
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

    def _setup_safe_globals(self):
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
        logger.debug(f"Safe Lua functions available: {', '.join(safe_functions)}")

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

            logger.info("Installed safe math and os libraries with determinism checking")

            # Setup safe file I/O libraries (always available)
            self._setup_file_io_libraries()
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

        # Setup safe file I/O libraries (always available)
        self._setup_file_io_libraries()

    def _setup_file_io_libraries(self):
        """Setup safe file I/O libraries restricted to working directory.

        Note: File and Json primitives are injected separately by the runtime
        (FilePrimitive and JsonPrimitive). This method only sets up the data
        format libraries (Csv, Tsv, Parquet, Hdf5, Excel).

        Security: Uses self.base_path which is fixed at initialization time,
        preventing security boundary expansion if working directory changes.
        """
        from tactus.utils.safe_file_library import (
            create_safe_csv_library,
            create_safe_excel_library,
            create_safe_hdf5_library,
            create_safe_parquet_library,
            create_safe_tsv_library,
        )

        # Use base_path fixed at initialization time (not os.getcwd())
        # This prevents security boundary expansion if working directory changes
        base_path = self.base_path

        # Inject data format libraries into Lua globals
        # Note: File and Json are handled by separate primitives in the runtime
        self.lua.globals()["Csv"] = self._dict_to_lua_table(create_safe_csv_library(base_path))
        self.lua.globals()["Tsv"] = self._dict_to_lua_table(create_safe_tsv_library(base_path))
        self.lua.globals()["Parquet"] = self._dict_to_lua_table(
            create_safe_parquet_library(base_path)
        )
        self.lua.globals()["Hdf5"] = self._dict_to_lua_table(create_safe_hdf5_library(base_path))
        self.lua.globals()["Excel"] = self._dict_to_lua_table(create_safe_excel_library(base_path))

        logger.debug(f"Injected data format libraries with base_path: {base_path}")

    def set_execution_context(self, context: Any):
        """
        Set or update execution context and refresh safe libraries.

        Args:
            context: ExecutionContext instance
        """
        self.execution_context = context
        # Re-setup safe globals with context
        self._setup_safe_globals()
        logger.debug("ExecutionContext attached to LuaSandbox")

    def inject_primitive(self, name: str, primitive_obj: Any):
        """
        Inject a Python primitive object into Lua globals.

        Args:
            name: Name of the primitive in Lua (e.g., "State", "Worker")
            primitive_obj: Python object to expose to Lua
        """
        self.lua.globals()[name] = primitive_obj
        logger.debug(f"Injected primitive '{name}' into Lua sandbox")

    def set_global(self, name: str, value: Any):
        """
        Set a global variable in Lua.

        Args:
            name: Name of the global variable
            value: Value to set (can be Python object, dict, etc.)
        """
        # Convert Python dicts to Lua tables if needed
        if isinstance(value, dict):
            lua_table = self.lua.table()
            for k, v in value.items():
                if isinstance(v, dict):
                    # Recursively convert nested dicts
                    lua_table[k] = self._dict_to_lua_table(v)
                else:
                    lua_table[k] = v
            self.lua.globals()[name] = lua_table
        else:
            self.lua.globals()[name] = value
        logger.debug(f"Set global '{name}' in Lua sandbox")

    def _dict_to_lua_table(self, d: dict):
        """Convert Python dict to Lua table recursively."""
        lua_table = self.lua.table()
        for k, v in d.items():
            if isinstance(v, dict):
                lua_table[k] = self._dict_to_lua_table(v)
            else:
                lua_table[k] = v
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
            logger.debug(f"Executing Lua code ({len(lua_code)} bytes)")
            result = self.lua.execute(lua_code)
            logger.debug("Lua execution completed successfully")
            return result

        except lupa.LuaError as e:
            # Lua runtime error
            error_msg = str(e)
            logger.error(f"Lua execution error: {error_msg}")
            raise LuaSandboxError(f"Lua runtime error: {error_msg}")

        except Exception as e:
            # Other Python exceptions
            logger.error(f"Sandbox execution error: {e}")
            raise LuaSandboxError(f"Sandbox error: {e}")

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

        except lupa.LuaError as e:
            error_msg = str(e)
            logger.error(f"Lua eval error: {error_msg}")
            raise LuaSandboxError(f"Lua eval error: {error_msg}")

    def get_global(self, name: str) -> Any:
        """Get a value from Lua global scope."""
        return self.lua.globals()[name]

    def create_lua_table(self, python_dict: Optional[Dict[str, Any]] = None) -> Any:
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
            lua_table[key] = value

        return lua_table

    def lua_table_to_dict(self, lua_table: Any) -> Dict[str, Any]:
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

        except Exception as e:
            logger.warning(f"Error converting Lua table to dict: {e}")
            # Fallback: try direct iteration
            try:
                for key in lua_table:
                    result[key] = lua_table[key]
            except Exception:  # noqa: E722
                pass

        return result
