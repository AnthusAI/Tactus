"""
DSL Handles - Lightweight placeholders returned by DSL declarations.

These handles are created during DSL parsing (before actual primitives exist)
and get connected to their real implementations at runtime via _enhance_handles().

Usage:
    # During parsing:
    Greeter = agent "greeter" { config }  # Returns AgentHandle("greeter")

    # During execution (callable syntax - preferred):
    Greeter()                             # Direct call
    Greeter({message = "Hello"})          # Call with options

    # Lookup syntax also works:
    Agent("greeter")()                    # Lookup + call
"""

import logging
from typing import Any, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from tactus.dspy.agent import DSPyAgentHandle
    from tactus.primitives.model import ModelPrimitive

logger = logging.getLogger(__name__)


def _convert_lua_table(lua_table: Any) -> Any:
    """
    Convert a lupa Lua table to a Python dict or list.

    Used to convert opts passed from Lua to Python methods.
    """
    if lua_table is None:
        return None

    # Check if it's a lupa table by checking for the items method
    if not hasattr(lua_table, "items"):
        # It's a primitive value (string, number, bool), return as-is
        return lua_table

    try:
        # Get all keys
        keys = list(lua_table.keys())

        # Empty table - return empty dict for opts (different from dsl_stubs which returns [])
        if not keys:
            return {}

        # Check if it's an array (all keys are consecutive integers starting from 1)
        if all(isinstance(k, int) for k in keys):
            sorted_keys = sorted(keys)
            if sorted_keys == list(range(1, len(keys) + 1)):
                # It's an array
                return [_convert_lua_table(lua_table[k]) for k in sorted_keys]

        # It's a dictionary
        result = {}
        for key, value in lua_table.items():
            # Recursively convert nested tables
            result[key] = _convert_lua_table(value)
        return result

    except (AttributeError, TypeError):
        # Fallback: return as-is
        return lua_table


class AgentHandle:
    """
    Lightweight handle returned by agent() DSL function.

    Created during DSL parsing, enhanced at runtime with actual AgentPrimitive.
    Supports callable syntax: agent() or agent({message = "..."})
    """

    def __init__(self, name: str):
        """
        Initialize agent handle.

        Args:
            name: Agent name (string identifier)
        """
        self.name = name
        self._primitive: Optional["DSPyAgentHandle"] = None
        self._execution_context: Optional[Any] = None
        logger.debug(f"AgentHandle created for '{name}'")

    def __call__(self, inputs: Any = None) -> Any:
        """
        Execute an agent turn using the callable interface.

        This is the unified callable interface that allows:
            result = worker({message = "Hello"})

        Args:
            inputs: Input dict with fields matching input_schema.
                   Default field 'message' is used as the user message.

        Returns:
            Result object with response and other fields

        Raises:
            RuntimeError: If handle not connected to primitive

        Example (Lua):
            result = worker({message = "Process this task"})
            print(result.response)
        """
        logger.debug(
            "[CHECKPOINT] AgentHandle '%s'.__call__ invoked, _primitive=%s, "
            "_execution_context=%s",
            self.name,
            self._primitive is not None,
            self._execution_context is not None,
        )
        if self._primitive is None:
            raise RuntimeError(
                f"Agent '{self.name}' initialization failed.\n"
                f"This should not happen with immediate agent creation.\n"
                f"Please report this as a bug with a minimal reproduction example."
            )
        # Convert Lua table to Python dict if needed
        converted_inputs = _convert_lua_table(inputs) if inputs is not None else None

        # Convenience: allow shorthand string calls in Lua:
        #   World("Hello") == World({message = "Hello"})
        if isinstance(converted_inputs, str):
            converted_inputs = {"message": converted_inputs}

        # If we have an execution context, checkpoint the agent call
        logger.debug(
            "[CHECKPOINT] AgentHandle '%s' called, has_execution_context=%s",
            self.name,
            self._execution_context is not None,
        )
        if self._execution_context is not None:

            def agent_call():
                return self._primitive(converted_inputs)

            # Capture source location from Lua if available
            source_info = None
            if (
                hasattr(self._execution_context, "lua_sandbox")
                and self._execution_context.lua_sandbox
            ):
                try:
                    lua = self._execution_context.lua_sandbox.lua
                    info = lua.eval("debug.getinfo(2, 'Sl')")
                    if info:
                        source_info = {
                            "file": info.get("source", "unknown"),
                            "line": info.get("currentline", 0),
                        }
                except Exception as error:
                    logger.debug("Could not capture source location: %s", error)

            logger.debug(
                "[CHECKPOINT] Creating checkpoint for agent '%s', type=agent_turn, source_info=%s",
                self.name,
                source_info,
            )
            result = self._execution_context.checkpoint(
                agent_call, checkpoint_type="agent_turn", source_info=source_info
            )
        else:
            # No execution context - call directly without checkpointing
            result = self._primitive(converted_inputs)

        # Convenience: expose the last agent output on the handle as `.output`
        # for Lua patterns like `agent(); return agent.output`.
        output_text = None
        if result is not None:
            for attr in ("response", "message"):
                try:
                    value = getattr(result, attr, None)
                except Exception:
                    value = None
                if isinstance(value, str):
                    output_text = value
                    break

            if output_text is None and isinstance(result, dict):
                for key in ("response", "message"):
                    value = result.get(key)
                    if isinstance(value, str):
                        output_text = value
                        break

            if output_text is None:
                output_text = str(result)

        self.output = output_text
        return result

    def _set_primitive(
        self, primitive: "DSPyAgentHandle", execution_context: Optional[Any] = None
    ) -> None:
        """
        Connect this handle to its actual primitive and execution context.

        Called by runtime._enhance_handles() after primitives are created.

        Args:
            primitive: The DSPyAgentHandle to delegate to
            execution_context: Optional execution context for checkpointing
        """
        self._primitive = primitive
        self._execution_context = execution_context
        logger.debug(
            "[CHECKPOINT] AgentHandle '%s' connected to primitive (checkpointing=%s, "
            "execution_context=%s)",
            self.name,
            "enabled" if execution_context else "disabled",
            execution_context,
        )

    def __repr__(self) -> str:
        connected = "connected" if self._primitive else "disconnected"
        return f"AgentHandle('{self.name}', {connected})"


class ModelHandle:
    """
    Lightweight handle returned by model() DSL function.

    Created during DSL parsing, enhanced at runtime with actual ModelPrimitive.
    Delegates .predict() calls to the real primitive.
    """

    def __init__(self, name: str):
        """
        Initialize model handle.

        Args:
            name: Model name (string identifier)
        """
        self.name = name
        self._primitive: Optional["ModelPrimitive"] = None
        logger.debug("ModelHandle created for '%s'", name)

    def predict(self, data: Any) -> Any:
        """
        Run model prediction (delegates to ModelPrimitive.predict()).

        Args:
            data: Input data for prediction

        Returns:
            Prediction result

        Raises:
            RuntimeError: If handle not connected to primitive
        """
        if self._primitive is None:
            raise RuntimeError(
                f"Model '{self.name}' initialization failed.\n"
                f"This should not happen - please report this as a bug."
            )
        converted_data = _convert_lua_table(data) if data is not None else None
        return self._primitive.predict(converted_data)

    def __call__(self, data: Any = None) -> Any:
        """
        Execute model prediction using the callable interface.

        This is the unified callable interface that allows:
            result = classifier({text = "Hello"})

        Args:
            data: Input data for prediction (format depends on model type)

        Returns:
            Model prediction result

        Raises:
            RuntimeError: If handle not connected to primitive

        Example (Lua):
            result = classifier({text = "This is great!"})
            print(result.label)       -- "positive"
        """
        if self._primitive is None:
            raise RuntimeError(
                f"Model '{self.name}' initialization failed.\n"
                f"This should not happen - please report this as a bug."
            )
        # Convert Lua table to Python dict if needed
        converted_data = _convert_lua_table(data) if data is not None else None
        return self._primitive(converted_data)

    def _set_primitive(self, primitive: "ModelPrimitive") -> None:
        """
        Connect this handle to its actual primitive.

        Called by runtime._enhance_handles() after primitives are created.

        Args:
            primitive: The ModelPrimitive to delegate to
        """
        self._primitive = primitive
        logger.debug("ModelHandle '%s' connected to primitive", self.name)

    def __repr__(self) -> str:
        connected = "connected" if self._primitive else "disconnected"
        return f"ModelHandle('{self.name}', {connected})"


class AgentLookup:
    """
    Agent lookup primitive - provides Agent("name") lookup functionality.

    Injected into Lua as 'Agent'. Callable to look up agents by name.
    """

    def __init__(self, registry: dict[str, AgentHandle]):
        """
        Initialize with reference to the agent registry.

        Args:
            registry: Dict mapping agent names to AgentHandle instances
        """
        self._registry = registry

    def __call__(self, name: str) -> AgentHandle:
        """
        Look up an agent by name.

        Args:
            name: Agent name to look up

        Returns:
            AgentHandle for the named agent

        Raises:
            ValueError: If agent not found

        Example (Lua):
            Agent("greeter")()  -- or Agent("greeter")({message = "Hello"})
        """
        if name not in self._registry:
            available = list(self._registry.keys())
            raise ValueError(f"Agent '{name}' not defined. Available agents: {available}")
        return self._registry[name]

    def __repr__(self) -> str:
        return f"AgentLookup({len(self._registry)} agents)"


class ModelLookup:
    """
    Model lookup primitive - provides Model("name") lookup functionality.

    Injected into Lua as 'Model'. Callable to look up models by name.
    """

    def __init__(self, registry: dict[str, ModelHandle]):
        """
        Initialize with reference to the model registry.

        Args:
            registry: Dict mapping model names to ModelHandle instances
        """
        self._registry = registry

    def __call__(self, name: str) -> ModelHandle:
        """
        Look up a model by name.

        Args:
            name: Model name to look up

        Returns:
            ModelHandle for the named model

        Raises:
            ValueError: If model not found

        Example (Lua):
            Model("classifier").predict(data)
        """
        if name not in self._registry:
            available = list(self._registry.keys())
            raise ValueError(f"Model '{name}' not defined. Available models: {available}")
        return self._registry[name]

    def __repr__(self) -> str:
        return f"ModelLookup({len(self._registry)} models)"
