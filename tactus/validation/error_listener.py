"""
ANTLR error listener for collecting syntax errors.
"""

from antlr4.error.ErrorListener import ErrorListener
from tactus.core.registry import ValidationMessage


class TactusErrorListener(ErrorListener):
    """Collects syntax errors from ANTLR parser."""

    def __init__(self):
        self.errors = []

    def syntaxError(self, recognizer, offendingSymbol, line, column, msg, e):
        """Called when parser encounters a syntax error."""
        self.errors.append(
            ValidationMessage(
                level="error", message=f"Syntax error: {msg}", location=(line, column)
            )
        )
