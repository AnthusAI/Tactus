"""
DSL Handles - Lightweight placeholders returned by DSL declarations.

These handles are created during DSL parsing (before actual primitives exist)
and get connected to their real implementations at runtime via _enhance_handles().

Usage:
    # During parsing:
    Greeter = agent "greeter" { config }  # Returns AgentHandle("greeter")

    # During execution:
    Agent("greeter").turn()               # Lookup + use
    Greeter.turn()                        # Direct use (same handle)
"""

import logging
from typing import Any, Optional, Dict, TYPE_CHECKING

if TYPE_CHECKING:
    from tactus.primitives.agent import AgentPrimitive
    from tactus.primitives.model import ModelPrimitive

logger = logging.getLogger(__name__)


class AgentHandle:
    """
    Lightweight handle returned by agent() DSL function.

    Created during DSL parsing, enhanced at runtime with actual AgentPrimitive.
    Delegates .turn() calls to the real primitive.
    """

    def __init__(self, name: str):
        """
        Initialize agent handle.

        Args:
            name: Agent name (string identifier)
        """
        self.name = name
        self._primitive: Optional["AgentPrimitive"] = None
        logger.debug(f"AgentHandle created for '{name}'")

    def turn(self, opts: Optional[Dict[str, Any]] = None) -> Any:
        """
        Execute one agent turn (delegates to AgentPrimitive.turn()).

        Args:
            opts: Optional dict with per-turn overrides:
                - inject: str - Message to inject for this turn
                - tools: List[str] - Tool names to use
                - temperature: float - Override temperature
                - max_tokens: int - Override max_tokens

        Returns:
            ResultPrimitive from agent turn

        Raises:
            RuntimeError: If handle not connected to primitive
        """
        if self._primitive is None:
            raise RuntimeError(
                f"Agent '{self.name}' not initialized. "
                f"This handle was created during DSL parsing but the runtime "
                f"hasn't connected it to the actual AgentPrimitive yet."
            )
        return self._primitive.turn(opts)

    def _set_primitive(self, primitive: "AgentPrimitive") -> None:
        """
        Connect this handle to its actual primitive.

        Called by runtime._enhance_handles() after primitives are created.

        Args:
            primitive: The AgentPrimitive to delegate to
        """
        self._primitive = primitive
        logger.debug(f"AgentHandle '{self.name}' connected to primitive")

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
        logger.debug(f"ModelHandle created for '{name}'")

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
                f"Model '{self.name}' not initialized. "
                f"This handle was created during DSL parsing but the runtime "
                f"hasn't connected it to the actual ModelPrimitive yet."
            )
        return self._primitive.predict(data)

    def _set_primitive(self, primitive: "ModelPrimitive") -> None:
        """
        Connect this handle to its actual primitive.

        Called by runtime._enhance_handles() after primitives are created.

        Args:
            primitive: The ModelPrimitive to delegate to
        """
        self._primitive = primitive
        logger.debug(f"ModelHandle '{self.name}' connected to primitive")

    def __repr__(self) -> str:
        connected = "connected" if self._primitive else "disconnected"
        return f"ModelHandle('{self.name}', {connected})"


class AgentLookup:
    """
    Agent lookup primitive - provides Agent("name") lookup functionality.

    Injected into Lua as 'Agent'. Callable to look up agents by name.
    """

    def __init__(self, registry: Dict[str, AgentHandle]):
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
            Agent("greeter").turn()
        """
        if name not in self._registry:
            available = list(self._registry.keys())
            raise ValueError(f"Agent '{name}' not defined. " f"Available agents: {available}")
        return self._registry[name]

    def __repr__(self) -> str:
        return f"AgentLookup({len(self._registry)} agents)"


class ModelLookup:
    """
    Model lookup primitive - provides Model("name") lookup functionality.

    Injected into Lua as 'Model'. Callable to look up models by name.
    """

    def __init__(self, registry: Dict[str, ModelHandle]):
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
            raise ValueError(f"Model '{name}' not defined. " f"Available models: {available}")
        return self._registry[name]

    def __repr__(self) -> str:
        return f"ModelLookup({len(self._registry)} models)"
