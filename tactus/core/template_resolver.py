"""
Template variable resolution for DSL strings.

Resolves template markers like {params.topic}, {state.count}, etc.
in system prompts, HITL messages, and other template strings.
"""

import re
from typing import Any, Optional


class TemplateResolver:
    """Resolves template variables in strings."""

    # Pattern matches {namespace.key} or {namespace.key.nested}
    TEMPLATE_PATTERN = re.compile(r"\{([a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)*)\}")

    def __init__(
        self,
        params: Optional[dict[str, Any]] = None,
        state: Optional[dict[str, Any]] = None,
        outputs: Optional[dict[str, Any]] = None,
        context: Optional[dict[str, Any]] = None,
        prepared: Optional[dict[str, Any]] = None,
        env: Optional[dict[str, str]] = None,
    ):
        """
        Initialize template resolver with available namespaces.

        Args:
            params: Input parameters
            state: Procedure state
            outputs: Output values (for return_prompt)
            context: Runtime context
            prepared: Agent prepare hook output
            env: Environment variables
        """
        self.namespaces = {
            "params": params or {},
            "state": state or {},
            "outputs": outputs or {},
            "context": context or {},
            "prepared": prepared or {},
            "env": env or {},
        }

    def resolve(self, template: str) -> str:
        """
        Resolve all template variables in a string.

        Args:
            template: String with {namespace.key} markers

        Returns:
            String with markers replaced by values

        Example:
            >>> resolver = TemplateResolver(params={"topic": "AI"})
            >>> resolver.resolve("Research: {params.topic}")
            "Research: AI"
        """
        if not template:
            return template

        def replace_match(match):
            path = match.group(1)
            value = self._get_value(path)
            if value is None:
                # Keep the marker if value not found
                return match.group(0)
            return str(value)

        return self.TEMPLATE_PATTERN.sub(replace_match, template)

    def _get_value(self, path: str) -> Any:
        """
        Get value from namespaces using dot notation.

        Args:
            path: Dot-separated path like "params.topic" or "state.count"

        Returns:
            Value at path, or None if not found
        """
        parts = path.split(".")
        if not parts:
            return None

        # First part is the namespace
        namespace_name = parts[0]
        namespace = self.namespaces.get(namespace_name)
        if namespace is None:
            return None

        # Navigate nested keys
        current = namespace
        for part in parts[1:]:
            if isinstance(current, dict):
                current = current.get(part)
            else:
                # Can't navigate further
                return None

            if current is None:
                return None

        return current


def resolve_template(
    template: str,
    params: Optional[dict[str, Any]] = None,
    state: Optional[dict[str, Any]] = None,
    outputs: Optional[dict[str, Any]] = None,
    context: Optional[dict[str, Any]] = None,
    prepared: Optional[dict[str, Any]] = None,
    env: Optional[dict[str, str]] = None,
) -> str:
    """
    Convenience function to resolve a template string.

    Args:
        template: String with {namespace.key} markers
        params: Input parameters
        state: Procedure state
        outputs: Output values
        context: Runtime context
        prepared: Agent prepare hook output
        env: Environment variables

    Returns:
        Resolved string
    """
    resolver = TemplateResolver(
        params=params,
        state=state,
        outputs=outputs,
        context=context,
        prepared=prepared,
        env=env,
    )
    return resolver.resolve(template)
