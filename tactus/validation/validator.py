"""
Tactus DSL validator.

Validates .tac files using ANTLR parser:
1. Lua syntax validation (via ANTLR parse tree)
2. Semantic validation (DSL construct recognition via visitor)
3. Registry validation (cross-reference checking)
"""

import logging
from enum import Enum
from typing import Optional

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

    def _build_parser(self, source: str) -> LuaParser:
        """
        Build a LuaParser for the provided source string.
        """
        source_stream = InputStream(source)
        lexer = LuaLexer(source_stream)
        token_stream = CommonTokenStream(lexer)
        return LuaParser(token_stream)

    def _result_with_errors(
        self,
        errors: list[ValidationMessage],
        warnings: Optional[list[ValidationMessage]] = None,
        registry: Optional[object] = None,
    ) -> ValidationResult:
        return ValidationResult(
            valid=False,
            errors=errors,
            warnings=warnings or [],
            registry=registry,
        )

    def _result_success(
        self,
        errors: Optional[list[ValidationMessage]] = None,
        warnings: Optional[list[ValidationMessage]] = None,
        registry: Optional[object] = None,
    ) -> ValidationResult:
        return ValidationResult(
            valid=not errors,
            errors=errors or [],
            warnings=warnings or [],
            registry=registry,
        )

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
        validation_errors: list[ValidationMessage] = []
        validation_warnings: list[ValidationMessage] = []
        validation_registry: Optional[object] = None

        try:
            # Phase 1: Lexical and syntactic analysis via ANTLR
            parser = self._build_parser(source)

            # Attach error listener to collect syntax errors
            syntax_error_collector = TactusErrorListener()
            parser.removeErrorListeners()
            parser.addErrorListener(syntax_error_collector)

            # Parse (start rule is 'start_' which expects chunk + EOF)
            lua_parse_tree = parser.start_()

            # Check for syntax errors
            if syntax_error_collector.syntax_errors:
                return self._result_with_errors(
                    errors=syntax_error_collector.syntax_errors,
                    warnings=[],
                    registry=None,
                )

            # Quick mode: just syntax check
            if mode == ValidationMode.QUICK:
                return self._result_success(errors=[], warnings=[], registry=None)

            # Phase 2: Semantic analysis (DSL validation)
            dsl_semantic_visitor = TactusDSLVisitor()
            dsl_semantic_visitor.visit(lua_parse_tree)

            # Combine visitor errors
            validation_errors = dsl_semantic_visitor.errors
            validation_warnings = dsl_semantic_visitor.warnings

            # Phase 3: Registry validation
            if not validation_errors:
                registry_validation_result = dsl_semantic_visitor.builder.validate()
                validation_errors.extend(registry_validation_result.errors)
                validation_warnings.extend(registry_validation_result.warnings)
                validation_registry = (
                    registry_validation_result.registry
                    if registry_validation_result.valid
                    else None
                )

            return self._result_success(
                errors=validation_errors,
                warnings=validation_warnings,
                registry=validation_registry,
            )

        except Exception as unexpected_exception:
            logger.error(
                "Validation failed with unexpected error: %s",
                unexpected_exception,
                exc_info=True,
            )
            validation_errors.append(
                ValidationMessage(
                    level="error",
                    message=f"Validation error: {unexpected_exception}",
                )
            )
            return self._result_with_errors(
                errors=validation_errors,
                warnings=validation_warnings,
                registry=None,
            )

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
            with open(file_path, "r") as source_file_handle:
                source_text = source_file_handle.read()
            return self.validate(source_text, mode)
        except FileNotFoundError:
            return self._result_with_errors(
                errors=[
                    ValidationMessage(
                        level="error",
                        message=f"File not found: {file_path}",
                    )
                ]
            )
        except Exception as exception:
            return self._result_with_errors(
                errors=[
                    ValidationMessage(
                        level="error",
                        message=f"Error reading file: {exception}",
                    )
                ]
            )
