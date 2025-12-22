"""
Tactus DSL validator.

Validates .tac files using ANTLR parser:
1. Lua syntax validation (via ANTLR parse tree)
2. Semantic validation (DSL construct recognition via visitor)
3. Registry validation (cross-reference checking)
"""

import logging
from enum import Enum
from typing import List

from antlr4 import InputStream, CommonTokenStream
from .generated.LuaLexer import LuaLexer
from .generated.LuaParser import LuaParser
from .semantic_visitor import TactusDSLVisitor
from .error_listener import TactusErrorListener
from tactus.core.registry import ValidationResult, ValidationMessage


logger = logging.getLogger(__name__)


class ValidationMode(str, Enum):
    """Validation mode."""

    QUICK = "quick"  # Fast syntax check only
    FULL = "full"  # Full semantic validation


class TactusValidator:
    """
    Validates .tac files using ANTLR parser.

    Uses formal Lua grammar for syntax validation and semantic
    visitor for DSL construct recognition.
    """

    def validate(
        self,
        source: str,
        mode: ValidationMode = ValidationMode.FULL,
    ) -> ValidationResult:
        """
        Validate a .tac file using ANTLR parser.

        Args:
            source: Lua DSL source code
            mode: Validation mode (quick or full)

        Returns:
            ValidationResult with errors, warnings, and registry
        """
        errors: List[ValidationMessage] = []
        warnings: List[ValidationMessage] = []
        registry = None

        try:
            # Phase 1: Lexical and syntactic analysis via ANTLR
            input_stream = InputStream(source)
            lexer = LuaLexer(input_stream)
            token_stream = CommonTokenStream(lexer)
            parser = LuaParser(token_stream)

            # Attach error listener to collect syntax errors
            error_listener = TactusErrorListener()
            parser.removeErrorListeners()
            parser.addErrorListener(error_listener)

            # Parse (start rule is 'start_' which expects chunk + EOF)
            tree = parser.start_()

            # Check for syntax errors
            if error_listener.errors:
                return ValidationResult(
                    valid=False, errors=error_listener.errors, warnings=[], registry=None
                )

            # Quick mode: just syntax check
            if mode == ValidationMode.QUICK:
                return ValidationResult(valid=True, errors=[], warnings=[], registry=None)

            # Phase 2: Semantic analysis (DSL validation)
            visitor = TactusDSLVisitor()
            visitor.visit(tree)

            # Combine visitor errors
            errors = visitor.errors
            warnings = visitor.warnings

            # Phase 3: Registry validation
            if not errors:
                result = visitor.builder.validate()
                errors.extend(result.errors)
                warnings.extend(result.warnings)
                registry = result.registry if result.valid else None
            else:
                registry = None

            return ValidationResult(
                valid=len(errors) == 0, errors=errors, warnings=warnings, registry=registry
            )

        except Exception as e:
            logger.error(f"Validation failed with unexpected error: {e}", exc_info=True)
            errors.append(
                ValidationMessage(
                    level="error",
                    message=f"Validation error: {e}",
                )
            )
            return ValidationResult(valid=False, errors=errors, warnings=warnings, registry=None)

    def validate_file(
        self,
        file_path: str,
        mode: ValidationMode = ValidationMode.FULL,
    ) -> ValidationResult:
        """
        Validate a .tac file from disk.

        Args:
            file_path: Path to .tac file
            mode: Validation mode

        Returns:
            ValidationResult
        """
        try:
            with open(file_path, "r") as f:
                source = f.read()
            return self.validate(source, mode)
        except FileNotFoundError:
            return ValidationResult(
                valid=False,
                errors=[
                    ValidationMessage(
                        level="error",
                        message=f"File not found: {file_path}",
                    )
                ],
                warnings=[],
                registry=None,
            )
        except Exception as e:
            return ValidationResult(
                valid=False,
                errors=[
                    ValidationMessage(
                        level="error",
                        message=f"Error reading file: {e}",
                    )
                ],
                warnings=[],
                registry=None,
            )
