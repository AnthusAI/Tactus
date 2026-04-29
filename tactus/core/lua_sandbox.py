"""
Lua Sandbox - Safe, restricted Lua execution environment.

Provides a sandboxed Lua runtime with:
- Data format libraries restricted to working directory (Csv, Tsv, Parquet, Hdf5, Excel)
- File and Json primitives injected separately by runtime
- require() available but restricted to host-registered modules, .tac files from
  working directory, and Tactus stdlib modules
- No dangerous operations (debug, io, loadfile, dofile removed)
- Only whitelisted primitives available
- Resource limits on CPU time and memory
"""

import logging
import os
import re
from typing import Any, Optional

try:
    import lupa
    from lupa import LuaRuntime

    LUPA_AVAILABLE = True
except ImportError:
    LUPA_AVAILABLE = False
    LuaRuntime = None

logger = logging.getLogger(__name__)
HOST_MODULE_NAME_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)*$")


def validate_python_module_name(name: str) -> None:
    """Validate a host-provided Lua require() module name."""

    if not name or not isinstance(name, str):
        raise ValueError("Module name must be a non-empty string")
    if name.startswith("tactus."):
        raise ValueError("Host modules cannot use the reserved 'tactus.' namespace")
    if not HOST_MODULE_NAME_PATTERN.match(name):
        raise ValueError(
            "Host module names must be dotted identifiers, e.g. 'plexus' or " "'vendor.module'"
        )


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
        python_modules: Optional[dict[str, Any]] = None,
    ):
        """
        Initialize the Lua sandbox.

        Args:
            execution_context: Optional ExecutionContext for checkpoint scope tracking
            strict_determinism: If True, raise errors instead of warnings for non-deterministic ops
            base_path: Optional base path for file operations and require(). Defaults to cwd.
            python_modules: Optional host-provided Python modules available via require().
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
        self.python_modules = {}
        for name, module in (python_modules or {}).items():
            try:
                validate_python_module_name(name)
            except ValueError as exc:
                raise LuaSandboxError(str(exc)) from exc
            self.python_modules[name] = module

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

        # Override byte-oriented Lua string functions with UTF-8-aware versions
        # to prevent multi-byte character corruption at the Lua/Python boundary
        self._setup_utf8_safe_strings()

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
            self.lua.execute("""
                if debug then
                    local safe_debug = {
                        getinfo = debug.getinfo
                    }
                    debug = safe_debug
                end
                """)
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
        self._stdlib_loader = StdlibModuleLoader(
            self,
            self.base_path,
            host_modules=self.python_modules,
        )
        host_loader_func = self._stdlib_loader.create_host_loader_function()
        stdlib_loader_func = self._stdlib_loader.create_loader_function()

        # Inject loader function into Lua
        self.lua.globals()["_tactus_host_python_loader"] = host_loader_func
        self.lua.globals()["_tactus_python_loader"] = stdlib_loader_func

        # Add to package.loaders (Lua 5.1) or package.searchers (Lua 5.2+)
        # Lupa uses LuaJIT which follows Lua 5.1 conventions
        self.lua.execute("""
            -- Add host and Python stdlib loaders to package.loaders.
            local loaders = package.loaders or package.searchers
            if loaders then
                -- Host modules are explicit capabilities provided by the
                -- embedding application. They run before .tac searchers so a
                -- local file cannot shadow require("plexus").
                local function host_python_searcher(modname)
                    local result = _tactus_host_python_loader(modname)
                    if result then
                        return function() return result end
                    end
                    return nil
                end

                -- Stdlib Python modules are fallback after .tac path loaders.
                local function stdlib_python_searcher(modname)
                    local result = _tactus_python_loader(modname)
                    if result then
                        return function() return result end
                    end
                    return nil
                end

                -- Insert host modules before filesystem searchers. Lua's first
                -- searcher handles package.preload, so index 2 preserves that.
                table.insert(loaders, 2, host_python_searcher)

                -- Append stdlib at end so .tac files are checked first.
                table.insert(loaders, stdlib_python_searcher)
            end
            """)

        logger.debug("Python host/stdlib loaders installed")

    def register_python_module(self, name: str, module: Any) -> None:
        """Register a host-provided Python module for Lua require().

        Registered modules are resolved by the same safe Python loader used for
        the Tactus stdlib. They are per-sandbox and do not expand filesystem
        search paths or enable arbitrary Python imports.
        """

        try:
            validate_python_module_name(name)
        except ValueError as exc:
            raise LuaSandboxError(str(exc)) from exc

        self.python_modules[name] = module
        if hasattr(self, "_stdlib_loader"):
            self._stdlib_loader.register_host_module(name, module)
        package = self.lua.globals()["package"]
        if package and package["loaded"]:
            package["loaded"][name] = None

    def _setup_safe_globals(self) -> None:
        """Setup safe global functions and utilities."""
        # Keep safe standard library functions
        # (These are already available by default, just documenting them)
        safe_global_symbols = {
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
        logger.debug("Safe Lua functions available: %s", ", ".join(safe_global_symbols))

        # Replace math and os libraries with safe versions if context available
        if self.execution_context is not None:
            self._install_context_safe_libraries()
            return  # Skip default os.date setup below

        self._install_fallback_os_date()

    def _install_context_safe_libraries(self) -> None:
        """Install safe math and os libraries based on execution context."""
        from tactus.utils.safe_libraries import (
            create_safe_math_library,
            create_safe_os_library,
        )

        def get_execution_context() -> Any:
            return self.execution_context

        safe_math_dict = create_safe_math_library(get_execution_context, self.strict_determinism)
        safe_os_dict = create_safe_os_library(get_execution_context, self.strict_determinism)

        safe_math_table = self._dict_to_lua_table(safe_math_dict)
        safe_os_table = self._dict_to_lua_table(safe_os_dict)

        self.lua.globals()["math"] = safe_math_table
        self.lua.globals()["os"] = safe_os_table

        logger.debug("Installed safe math and os libraries with determinism checking")

    def _install_fallback_os_date(self) -> None:
        """Install a safe os.date() fallback when no execution context is available."""
        safe_os_table = self._build_fallback_os_table()
        self.lua.globals()["os"] = safe_os_table
        logger.debug("Added safe os.date() function")

    def _build_fallback_os_table(self) -> Any:
        """Build a Lua os table with a safe date() implementation."""
        from datetime import datetime, timezone

        def safe_date(format_string: Optional[str] = None) -> str:
            """Safe implementation of os.date() for timestamp generation."""
            now = datetime.now(timezone.utc)
            if format_string is None:
                # Return default format like Lua's os.date()
                return now.strftime("%a %b %d %H:%M:%S %Y")
            if format_string == "%Y-%m-%dT%H:%M:%SZ":
                # ISO 8601 format
                return now.strftime("%Y-%m-%dT%H:%M:%SZ")
            # Support Python strftime formats
            try:
                return now.strftime(format_string)
            except Exception:  # noqa: E722
                return now.strftime("%a %b %d %H:%M:%S %Y")

        return self.lua.table(date=safe_date)

    def _setup_utf8_safe_strings(self) -> None:
        """Override Lua's byte-oriented string functions with UTF-8-aware versions.

        Lua's built-in string library treats strings as raw byte sequences. Operations
        like string.sub() can split multi-byte UTF-8 characters (e.g. em-dashes are
        3 bytes: 0xE2 0x80 0x94), producing invalid UTF-8. When lupa converts these
        corrupted strings back to Python, it raises UnicodeDecodeError.

        This method injects UTF-8-aware replacements for the most dangerous operations:
        - string.sub: character-based substring instead of byte-based
        - string.len: character count instead of byte count
        - string.reverse: reverses characters, not bytes

        A utf8_clean() global is also provided as a safety net for any strings that
        may have been corrupted by operations we don't override.
        """
        self.lua.execute("""
            -- UTF-8 iterator: yields start_pos, char_string for each character
            local function utf8_chars(s)
                local chars = {}
                local i = 1
                local len = #s  -- byte length
                while i <= len do
                    local b = string.byte(s, i)
                    local char_len
                    if b < 128 then
                        char_len = 1
                    elseif b >= 194 and b <= 223 then
                        char_len = 2
                    elseif b >= 224 and b <= 239 then
                        char_len = 3
                    elseif b >= 240 and b <= 244 then
                        char_len = 4
                    else
                        -- Invalid start byte, treat as single byte
                        char_len = 1
                    end
                    -- Clamp to string boundary
                    if i + char_len - 1 > len then
                        char_len = len - i + 1
                    end
                    chars[#chars + 1] = _orig_string_sub(s, i, i + char_len - 1)
                    i = i + char_len
                end
                return chars
            end

            -- Save originals before overriding
            _orig_string_sub = string.sub
            _orig_string_len = string.len
            _orig_string_rev = string.reverse
            _orig_string_byte = string.byte

            -- UTF-8 aware string.sub
            string.sub = function(s, i, j)
                if type(s) ~= "string" then return _orig_string_sub(s, i, j) end
                -- Fast path: ASCII-only strings have no multi-byte characters
                if not s:find("[\\128-\\255]") then
                    return _orig_string_sub(s, i, j)
                end
                local chars = utf8_chars(s)
                local n = #chars
                j = j or n
                -- Handle negative indices (Lua convention)
                if i < 0 then i = n + 1 + i end
                if j < 0 then j = n + 1 + j end
                if i < 1 then i = 1 end
                if j > n then j = n end
                if i > j then return "" end
                local parts = {}
                for idx = i, j do
                    parts[#parts + 1] = chars[idx]
                end
                return table.concat(parts)
            end

            -- UTF-8 aware string.len
            string.len = function(s)
                if type(s) ~= "string" then return _orig_string_len(s) end
                if not s:find("[\\128-\\255]") then
                    return _orig_string_len(s)
                end
                return #utf8_chars(s)
            end

            -- UTF-8 aware string.reverse
            string.reverse = function(s)
                if type(s) ~= "string" then return _orig_string_rev(s) end
                if not s:find("[\\128-\\255]") then
                    return _orig_string_rev(s)
                end
                local chars = utf8_chars(s)
                local parts = {}
                for i = #chars, 1, -1 do
                    parts[#parts + 1] = chars[i]
                end
                return table.concat(parts)
            end

            -- Global utility: clean invalid UTF-8 sequences in a string
            function utf8_clean(s)
                if type(s) ~= "string" then return s end
                if not s:find("[\\128-\\255]") then return s end
                local result = {}
                local i = 1
                local len = #s
                while i <= len do
                    local b = string.byte(s, i)
                    if b < 128 then
                        result[#result + 1] = _orig_string_sub(s, i, i)
                        i = i + 1
                    elseif b >= 194 and b <= 223 then
                        if i + 1 <= len
                            and string.byte(s, i+1) >= 128
                            and string.byte(s, i+1) <= 191 then
                            result[#result + 1] = _orig_string_sub(s, i, i+1)
                            i = i + 2
                        else
                            result[#result + 1] = "?"
                            i = i + 1
                        end
                    elseif b >= 224 and b <= 239 then
                        if i + 2 <= len
                            and string.byte(s, i+1) >= 128 and string.byte(s, i+1) <= 191
                            and string.byte(s, i+2) >= 128 and string.byte(s, i+2) <= 191 then
                            result[#result + 1] = _orig_string_sub(s, i, i+2)
                            i = i + 3
                        else
                            result[#result + 1] = "?"
                            i = i + 1
                        end
                    elseif b >= 240 and b <= 244 then
                        if i + 3 <= len
                            and string.byte(s, i+1) >= 128 and string.byte(s, i+1) <= 191
                            and string.byte(s, i+2) >= 128 and string.byte(s, i+2) <= 191
                            and string.byte(s, i+3) >= 128 and string.byte(s, i+3) <= 191 then
                            result[#result + 1] = _orig_string_sub(s, i, i+3)
                            i = i + 4
                        else
                            result[#result + 1] = "?"
                            i = i + 1
                        end
                    else
                        result[#result + 1] = "?"
                        i = i + 1
                    end
                end
                return table.concat(result)
            end
        """)
        logger.debug("Installed UTF-8 safe string overrides (sub, len, reverse, utf8_clean)")

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
