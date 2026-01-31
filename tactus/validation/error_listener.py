"""
ANTLR error listener for collecting syntax errors.
"""

from antlr4.error.ErrorListener import ErrorListener
from tactus.core.registry import ValidationMessage


class TactusErrorListener(ErrorListener):
    """Collects syntax errors from ANTLR parser."""

    def __init__(self) -> None:
        self.syntax_errors: list[ValidationMessage] = []
        # Backward-compatible alias used by formatter/tests.
        self.errors = self.syntax_errors

    def syntaxError(
        self,
        parser,
        offending_token,
        line_number: int,
        column_number: int,
        antlr_error_message: str,
        antlr_exception,
    ) -> None:
        """Called when parser encounters a syntax error."""
        del parser, offending_token, antlr_exception
        self.syntax_errors.append(
            ValidationMessage(
                level="error",
                message=f"Syntax error: {antlr_error_message}",
                location=(line_number, column_number),
            )
        )
