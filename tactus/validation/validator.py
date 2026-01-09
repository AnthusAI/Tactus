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

    def _maybe_transform_script_mode(self, source: str) -> str:
        """Check if source needs script mode transformation and apply it."""
        import re

        # Remove comments before checking
        source_no_comments = re.sub(r"--.*$", "", source, flags=re.MULTILINE)
        has_top_level_io = (
            "input {" in source_no_comments
            or "input(" in source_no_comments
            or "output {" in source_no_comments
            or "output(" in source_no_comments
        )

        if has_top_level_io:
            logger.debug("Script mode detected - transforming source for validation")
            return self._transform_to_procedure(source)
        return source

    def _transform_to_procedure(self, source: str) -> str:
        """Transform script mode source to wrap body in implicit Procedure."""
        import re

        lines = source.split("\n")
        split_index = None

        # Patterns that start declarations (not executable)
        declaration_start_patterns = [
            r"^\s*(input|output|Mocks|Stages)\s*[{\(]",
            r"^\s*Specifications\s*\(",
            r"^\s*Evaluations\s*\(",
            r"^\s*[a-zA-Z_]\w*\s*=\s*Agent\s*{",
            r'^\s*Agent\s+"[^"]*"\s*{',
            r"^\s*[a-zA-Z_]\w*\s*=\s*Tool\s*{",
            r'^\s*Tool\s+"[^"]*"\s*{',
            r"^\s*[a-zA-Z_]\w*\s*=\s*Toolset\s*{",
            r'^\s*Toolset\s+"[^"]*"\s*{',
            r"^\s*[a-zA-Z_]\w*\s*=\s*Model\s*{",
            r'^\s*Model\s+"[^"]*"\s*{',
            r"^\s*[a-zA-Z_]\w*\s*=\s*tactus\.",
        ]

        always_declaration_patterns = [
            r"^\s*--",  # Comments
            r"^\s*$",  # Empty lines
        ]

        # Track brace/paren depth to handle multi-line blocks
        brace_depth = 0
        paren_depth = 0
        in_declaration_block = False
        in_multiline_comment = False

        for i, line in enumerate(lines):
            # Track multi-line comment state
            if "--[[" in line:
                in_multiline_comment = True
            if in_multiline_comment:
                if "]]" in line:
                    in_multiline_comment = False
                continue

            if any(re.match(p, line) for p in always_declaration_patterns):
                continue
            starts_declaration = any(re.match(p, line) for p in declaration_start_patterns)
            if starts_declaration:
                in_declaration_block = True
            # Track both braces and parentheses
            brace_depth += line.count("{") - line.count("}")
            paren_depth += line.count("(") - line.count(")")
            if in_declaration_block:
                # Declaration block ends when both braces and parens are balanced
                if brace_depth == 0 and paren_depth == 0:
                    in_declaration_block = False
                continue
            split_index = i
            break

        if split_index is None:
            return source

        # Find where body ends and trailing declarations begin
        end_index = len(lines)
        for i in range(split_index, len(lines)):
            line = lines[i]
            # Check for trailing declaration markers BEFORE checking always_declaration_patterns
            # because the BDD comment would otherwise match the general comment pattern
            if re.match(r"^\s*--\s*BDD\s+Specifications", line, re.IGNORECASE):
                end_index = i
                break
            if re.match(r"^\s*--\s*Pydantic\s+Evals", line, re.IGNORECASE):
                end_index = i
                break
            if re.match(r"^\s*Specifications\s*\(", line):
                end_index = i
                break
            if re.match(r"^\s*Evaluations\s*\(", line):
                end_index = i
                break
            # Check for subsequent Procedure declarations (named procedures after script mode)
            if re.match(r"^\s*(\w+\s*=\s*)?Procedure\s+", line):
                end_index = i
                break
            # Skip empty lines and other comments
            if any(re.match(p, line) for p in always_declaration_patterns):
                continue

        declarations_before = "\n".join(lines[:split_index])
        body = "\n".join(lines[split_index:end_index])
        declarations_after = "\n".join(lines[end_index:])

        # Indent body for Procedure function
        indented_body = "\n".join("        " + line for line in body.split("\n"))

        transformed = f"""{declarations_before}

main = Procedure "main" {{
    function(input)
{indented_body}
    end
}}

{declarations_after}"""
        logger.debug(
            f"Script mode: transformed source (body from line {split_index} to {end_index})"
        )
        return transformed

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
            # Apply script mode transformation if needed (before ANTLR parsing)
            # This ensures script mode files are valid Lua syntax for the parser
            source = self._maybe_transform_script_mode(source)

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
