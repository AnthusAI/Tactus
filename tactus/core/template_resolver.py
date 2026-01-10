"""
Template resolution utilities for agent prompts.

Supports two modes:
- ``jinja2`` (default): renders strings with Jinja2 using StrictUndefined
- ``plain``: returns the template unchanged

Only the context explicitly provided by callers is available to templates.
"""

from __future__ import annotations

import logging
from typing import Any, Mapping

from jinja2 import Environment, StrictUndefined, TemplateError

logger = logging.getLogger(__name__)


class TemplateResolver:
    """Render prompt templates using a constrained context."""

    VALID_MODES = {"jinja2", "plain"}

    def __init__(self, mode: str = "jinja2"):
        if mode not in self.VALID_MODES:
            raise ValueError(f"Unknown template mode '{mode}'. Expected one of {self.VALID_MODES}.")

        self.mode = mode
        self._env = None

        if mode == "jinja2":
            # StrictUndefined prevents silent fallback to empty strings when a variable is missing.
            self._env = Environment(undefined=StrictUndefined, autoescape=False, trim_blocks=True)

    def render(self, template: Any, context: Mapping[str, Any] | None = None) -> Any:
        """
        Render a template string with the provided context.

        Non-string inputs are returned unchanged so callers can safely pass
        configuration values without pre-checking their types.
        """
        if not isinstance(template, str):
            return template

        if not template or self.mode == "plain":
            return template

        try:
            assert self._env is not None
            return self._env.from_string(template).render(**(context or {}))
        except TemplateError as exc:
            logger.warning(f"Template rendering failed ({exc}). Returning template unchanged.")
            return template
        except Exception as exc:  # pragma: no cover - defensive guard
            logger.error(f"Unexpected template rendering error: {exc}")
            return template


def render_template(template: Any, context: Mapping[str, Any] | None = None, mode: str = "jinja2"):
    """Convenience wrapper for one-off renders."""
    return TemplateResolver(mode=mode).render(template, context)
