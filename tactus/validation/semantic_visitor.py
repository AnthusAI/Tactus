"""
Semantic visitor for Tactus DSL.

Walks the ANTLR parse tree and recognizes DSL patterns,
extracting declarations without executing code.
"""

import logging
from typing import Any, Optional

from .generated.LuaParser import LuaParser
from .generated.LuaParserVisitor import LuaParserVisitor
from tactus.core.registry import RegistryBuilder, ValidationMessage


logger = logging.getLogger(__name__)


class TactusDSLVisitor(LuaParserVisitor):
    """
    Walks ANTLR parse tree and recognizes DSL patterns.
    Does NOT execute code - only analyzes structure.
    """

    DSL_FUNCTIONS = {
        "name",
        "version",
        "description",
        "agent",
        "model",
        "procedure",
        "prompt",
        "hitl",
        "stages",
        "specification",
        "specifications",  # Gherkin BDD specs
        "step",  # Custom step definitions
        "evaluation",  # Evaluation configuration
        "evaluations",  # Pydantic Evals configuration
        "default_provider",
        "default_model",
        "return_prompt",
        "error_prompt",
        "status_prompt",
        "async",
        "max_depth",
        "max_turns",
    }

    def __init__(self):
        self.builder = RegistryBuilder()
        self.errors = []
        self.warnings = []
        self.current_line = 0
        self.current_col = 0

    def visitFunctioncall(self, ctx: LuaParser.FunctioncallContext):
        """Recognize and process DSL function calls."""
        try:
            func_name = self._extract_function_name(ctx)

            if func_name in self.DSL_FUNCTIONS:
                # Extract line/column for error reporting
                if ctx.start:
                    self.current_line = ctx.start.line
                    self.current_col = ctx.start.column

                # Process the DSL call
                try:
                    self._process_dsl_call(func_name, ctx)
                except Exception as e:
                    self.errors.append(
                        ValidationMessage(
                            level="error",
                            message=f"Error processing {func_name}: {e}",
                            location=(self.current_line, self.current_col),
                            declaration=func_name,
                        )
                    )
        except Exception as e:
            logger.debug(f"Error in visitFunctioncall: {e}")

        return self.visitChildren(ctx)

    def _extract_function_name(self, ctx: LuaParser.FunctioncallContext) -> Optional[str]:
        """Extract function name from parse tree."""
        # The function name is the first child of functioncall
        # Look for a terminal node with text
        for i in range(ctx.getChildCount()):
            child = ctx.getChild(i)
            if hasattr(child, "symbol"):
                # It's a terminal node
                text = child.getText()
                if text and text.isidentifier():
                    return text

        # Fallback: try varOrExp approach
        if ctx.varOrExp():
            var_or_exp = ctx.varOrExp()
            # varOrExp: var | '(' exp ')'
            if var_or_exp.var():
                var_ctx = var_or_exp.var()
                # var: (NAME | '(' exp ')' varSuffix) varSuffix*
                if var_ctx.NAME():
                    return var_ctx.NAME().getText()

        return None

    def _process_dsl_call(self, func_name: str, ctx: LuaParser.FunctioncallContext):
        """Extract arguments and register declaration."""
        args = self._extract_arguments(ctx)

        if func_name == "name":
            if args and len(args) >= 1:
                self.builder.set_name(args[0])
        elif func_name == "version":
            if args and len(args) >= 1:
                self.builder.set_version(args[0])
        elif func_name == "agent":
            if args and len(args) >= 2:
                self.builder.register_agent(args[0], args[1] if isinstance(args[1], dict) else {})
        elif func_name == "model":
            if args and len(args) >= 2:
                self.builder.register_model(args[0], args[1] if isinstance(args[1], dict) else {})
        elif func_name == "procedure":
            # For procedure, mark that it exists and extract inline input/output/state if present
            self.builder.set_procedure(True)

            # Check if first argument is a table constructor with input/output/state
            if args and len(args) >= 1 and isinstance(args[0], dict):
                config = args[0]

                # Extract inline input schema
                if "input" in config and isinstance(config["input"], dict):
                    self.builder.register_input_schema(config["input"])

                # Extract inline output schema
                if "output" in config and isinstance(config["output"], dict):
                    self.builder.register_output_schema(config["output"])

                # Extract inline state schema
                if "state" in config and isinstance(config["state"], dict):
                    self.builder.register_state_schema(config["state"])
        elif func_name == "prompt":
            if args and len(args) >= 2:
                self.builder.register_prompt(args[0], args[1])
        elif func_name == "hitl":
            if args and len(args) >= 2:
                self.builder.register_hitl(args[0], args[1] if isinstance(args[1], dict) else {})
        elif func_name == "stages":
            if args:
                # stages() can take multiple string arguments
                self.builder.set_stages(args)
        elif func_name == "specification":
            if args and len(args) >= 2:
                self.builder.register_specification(
                    args[0], args[1] if isinstance(args[1], list) else []
                )
        elif func_name == "specifications":
            # specifications([[ Gherkin text ]])
            if args and len(args) >= 1:
                self.builder.register_specifications(args[0])
        elif func_name == "step":
            # step("step text", function() ... end)
            if args and len(args) >= 2:
                self.builder.register_custom_step(args[0], args[1])
        elif func_name == "evaluation":
            # evaluation({ runs = 10, parallel = true })
            if args and len(args) >= 1:
                self.builder.set_evaluation_config(args[0] if isinstance(args[0], dict) else {})
        elif func_name == "evaluations":
            # evaluations({ dataset = {...}, evaluators = {...} })
            if args and len(args) >= 1:
                self.builder.register_evaluations(args[0] if isinstance(args[0], dict) else {})
        elif func_name == "default_provider":
            if args and len(args) >= 1:
                self.builder.set_default_provider(args[0])
        elif func_name == "default_model":
            if args and len(args) >= 1:
                self.builder.set_default_model(args[0])
        elif func_name == "return_prompt":
            if args and len(args) >= 1:
                self.builder.set_return_prompt(args[0])
        elif func_name == "error_prompt":
            if args and len(args) >= 1:
                self.builder.set_error_prompt(args[0])
        elif func_name == "status_prompt":
            if args and len(args) >= 1:
                self.builder.set_status_prompt(args[0])
        elif func_name == "async":
            if args and len(args) >= 1:
                self.builder.set_async(args[0])
        elif func_name == "max_depth":
            if args and len(args) >= 1:
                self.builder.set_max_depth(args[0])
        elif func_name == "max_turns":
            if args and len(args) >= 1:
                self.builder.set_max_turns(args[0])

    def _extract_arguments(self, ctx: LuaParser.FunctioncallContext) -> list:
        """Extract function arguments from parse tree."""
        args = []

        # functioncall has args() children
        # args: '(' explist? ')' | tableconstructor | LiteralString

        args_list = ctx.args()
        if not args_list:
            return args

        for args_ctx in args_list:
            # Check for different argument types
            if args_ctx.explist():
                # Regular function call with expression list
                explist = args_ctx.explist()
                for exp in explist.exp():
                    value = self._parse_expression(exp)
                    if value is not None:
                        args.append(value)
            elif args_ctx.tableconstructor():
                # Table constructor argument
                table = self._parse_table_constructor(args_ctx.tableconstructor())
                args.append(table)
            elif args_ctx.string():
                # String literal argument
                string_val = self._parse_string(args_ctx.string())
                args.append(string_val)

        return args

    def _parse_expression(self, ctx: LuaParser.ExpContext) -> Any:
        """Parse an expression to a Python value."""
        if not ctx:
            return None

        # Check for literals
        if ctx.number():
            return self._parse_number(ctx.number())
        elif ctx.string():
            return self._parse_string(ctx.string())
        elif ctx.NIL():
            return None
        elif ctx.FALSE():
            return False
        elif ctx.TRUE():
            return True
        elif ctx.tableconstructor():
            return self._parse_table_constructor(ctx.tableconstructor())

        # For other expressions, return None (can't evaluate without execution)
        return None

    def _parse_string(self, ctx: LuaParser.StringContext) -> str:
        """Parse string context to Python string."""
        if not ctx:
            return ""

        # string has NORMALSTRING, CHARSTRING, or LONGSTRING
        if ctx.NORMALSTRING():
            return self._parse_string_token(ctx.NORMALSTRING())
        elif ctx.CHARSTRING():
            return self._parse_string_token(ctx.CHARSTRING())
        elif ctx.LONGSTRING():
            return self._parse_string_token(ctx.LONGSTRING())

        return ""

    def _parse_string_token(self, token) -> str:
        """Parse string token to Python string."""
        text = token.getText()

        # Handle different Lua string formats
        if text.startswith("[[") and text.endswith("]]"):
            # Long string literal
            return text[2:-2]
        elif text.startswith('"') and text.endswith('"'):
            # Double-quoted string
            content = text[1:-1]
            content = content.replace("\\n", "\n")
            content = content.replace("\\t", "\t")
            content = content.replace('\\"', '"')
            content = content.replace("\\\\", "\\")
            return content
        elif text.startswith("'") and text.endswith("'"):
            # Single-quoted string
            content = text[1:-1]
            content = content.replace("\\n", "\n")
            content = content.replace("\\t", "\t")
            content = content.replace("\\'", "'")
            content = content.replace("\\\\", "\\")
            return content

        return text

    def _parse_table_constructor(self, ctx: LuaParser.TableconstructorContext) -> dict:
        """Parse Lua table constructor to Python dict."""
        result = {}
        array_items = []

        if not ctx or not ctx.fieldlist():
            # Empty table
            return []  # Return empty list for empty tables (matches runtime behavior)

        fieldlist = ctx.fieldlist()
        for field in fieldlist.field():
            # field: '[' exp ']' '=' exp | NAME '=' exp | exp
            if field.NAME():
                # Named field: NAME '=' exp
                key = field.NAME().getText()
                value = self._parse_expression(field.exp(0))
                result[key] = value
            elif len(field.exp()) == 2:
                # Indexed field: '[' exp ']' '=' exp
                # Skip for now (complex)
                pass
            elif len(field.exp()) == 1:
                # Array element: exp
                value = self._parse_expression(field.exp(0))
                array_items.append(value)

        # If we only have array items, return as list
        if array_items and not result:
            return array_items

        # If we have both, prefer dict (shouldn't happen in DSL)
        if array_items:
            # Mixed table - add array items with numeric keys
            for i, item in enumerate(array_items, 1):
                result[i] = item

        return result if result else []

    def _parse_number(self, ctx: LuaParser.NumberContext) -> float:
        """Parse Lua number to Python number."""
        text = ctx.getText()

        # Try integer first
        try:
            return int(text)
        except ValueError:
            pass

        # Try float
        try:
            return float(text)
        except ValueError:
            pass

        # Try hex
        if text.startswith("0x") or text.startswith("0X"):
            try:
                return int(text, 16)
            except ValueError:
                pass

        return 0
