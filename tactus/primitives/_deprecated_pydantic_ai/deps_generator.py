"""
Dynamic AgentDeps generation for dependency injection.

This module provides functionality to generate AgentDeps subclasses
that include both framework dependencies and user-declared dependencies.
"""

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


def generate_agent_deps_class(user_dependencies: Optional[Dict[str, Any]] = None) -> type:
    """
    Generate a dynamic AgentDeps class with user-declared dependencies.

    Args:
        user_dependencies: Dict mapping dependency name to resource instance
                          (HTTP clients, DB connections, etc.)

    Returns:
        A dataclass type that extends the base AgentDeps with user dependencies

    Example:
        >>> http_client = httpx.AsyncClient()
        >>> DepsClass = generate_agent_deps_class({"weather_api": http_client})
        >>> deps = DepsClass(
        ...     state_primitive=state,
        ...     context=ctx,
        ...     system_prompt_template="...",
        ...     weather_api=http_client
        ... )
    """
    if not user_dependencies:
        # No user dependencies - return base AgentDeps
        from tactus.primitives.agent import AgentDeps

        return AgentDeps

    logger.debug(f"Generating AgentDeps with user dependencies: {list(user_dependencies.keys())}")

    # Create a dynamic class by building the fields dict for dataclass
    # This is necessary because dataclasses need fields to be defined at class creation time
    from dataclasses import make_dataclass

    # Build field specifications: (name, type, default)
    # NOTE: Fields without defaults must come before fields with defaults
    fields = [
        ("state_primitive", Any),
        ("context", Dict[str, Any]),
        ("system_prompt_template", str),
    ]

    # Add user dependency fields (required, no defaults - must be before fields with defaults)
    for dep_name in user_dependencies.keys():
        fields.append((dep_name, Any))

    # Add fields with defaults last
    fields.append(("output_schema_guidance", Optional[str], None))

    # Create the dataclass dynamically
    GeneratedAgentDeps = make_dataclass(
        "GeneratedAgentDeps",
        fields,
        namespace={"__doc__": "Generated AgentDeps with user-declared dependencies."},
    )

    return GeneratedAgentDeps


def create_agent_deps_instance(
    deps_class: type,
    state_primitive: Any,
    context: Dict[str, Any],
    system_prompt_template: str,
    output_schema_guidance: Optional[str] = None,
    user_dependencies: Optional[Dict[str, Any]] = None,
) -> Any:
    """
    Create an instance of the generated AgentDeps class.

    Args:
        deps_class: The AgentDeps class (base or generated)
        state_primitive: StatePrimitive instance
        context: Procedure context dict
        system_prompt_template: System prompt template string
        output_schema_guidance: Optional output schema guidance
        user_dependencies: Dict of user dependency instances

    Returns:
        AgentDeps instance with all dependencies
    """
    # Start with framework dependencies
    kwargs = {
        "state_primitive": state_primitive,
        "context": context,
        "system_prompt_template": system_prompt_template,
        "output_schema_guidance": output_schema_guidance,
    }

    # Add user dependencies if present
    if user_dependencies:
        kwargs.update(user_dependencies)

    return deps_class(**kwargs)
