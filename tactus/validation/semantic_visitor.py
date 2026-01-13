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
        "Agent",  # CamelCase
        "Model",  # CamelCase
        "Procedure",  # CamelCase
        "Prompt",  # CamelCase
        "Hitl",  # CamelCase
        "Stages",  # CamelCase
        "Specification",  # CamelCase
        "Specifications",  # CamelCase - Gherkin BDD specs
        "Step",  # CamelCase - Custom step definitions
        "Evaluation",  # CamelCase - Evaluation configuration
        "Evaluations",  # CamelCase - Pydantic Evals configuration
        "default_provider",
        "default_model",
        "return_prompt",
        "error_prompt",
        "status_prompt",
        "async",
        "max_depth",
        "max_turns",
        "Tool",  # CamelCase - Lua-defined tools
        "Toolset",  # CamelCase - Added for toolsets
        "input",  # lowercase - top-level input schema for script mode
        "output",  # lowercase - top-level output schema for script mode
    }

    def __init__(self):
        self.builder = RegistryBuilder()
        self.errors = []
        self.warnings = []
        self.current_line = 0
        self.current_col = 0
        self.in_function_body = False  # Track if we're inside a function body

    def visitFunctiondef(self, ctx):
        """Track when entering/exiting function definitions."""
        # Set flag when entering function body
        old_in_function = self.in_function_body
        self.in_function_body = True
        try:
            result = super().visitChildren(ctx)
        finally:
            # Restore previous state when exiting
            self.in_function_body = old_in_function
        return result

    def visitStat(self, ctx: LuaParser.StatContext):
        """Handle statement nodes including assignments."""
        # Check if this is an assignment statement
        if ctx.varlist() and ctx.explist():
            # This is an assignment: varlist '=' explist
            varlist = ctx.varlist()
            explist = ctx.explist()

            # Get the variable name
            if varlist.var() and len(varlist.var()) > 0:
                var = varlist.var()[0]
                if var.NAME():
                    var_name = var.NAME().getText()

                    # Check if this is a DSL setting assignment
                    if var_name in [
                        "default_provider",
                        "default_model",
                        "return_prompt",
                        "error_prompt",
                        "status_prompt",
                        "async",
                        "max_depth",
                        "max_turns",
                    ]:
                        # Get the value from explist
                        if explist.exp() and len(explist.exp()) > 0:
                            exp = explist.exp()[0]
                            value = self._extract_literal_value(exp)

                            # Process the assignment like a function call
                            if var_name == "default_provider":
                                self.builder.set_default_provider(value)
                            elif var_name == "default_model":
                                self.builder.set_default_model(value)
                            elif var_name == "return_prompt":
                                self.builder.set_return_prompt(value)
                            elif var_name == "error_prompt":
                                self.builder.set_error_prompt(value)
                            elif var_name == "status_prompt":
                                self.builder.set_status_prompt(value)
                            elif var_name == "async":
                                self.builder.set_async(value)
                            elif var_name == "max_depth":
                                self.builder.set_max_depth(value)
                            elif var_name == "max_turns":
                                self.builder.set_max_turns(value)
                    else:
                        # Check for assignment-based DSL declarations
                        # e.g., greeter = Agent {...}, done = Tool {...}
                        if explist.exp() and len(explist.exp()) > 0:
                            exp = explist.exp()[0]
                            self._check_assignment_based_declaration(var_name, exp)

        # Continue visiting children
        return self.visitChildren(ctx)

    def _check_assignment_based_declaration(self, var_name: str, exp):
        """Check if an assignment is a DSL declaration like 'greeter = Agent {...}'."""
        # Look for prefixexp with functioncall pattern: Agent {...}
        if exp.prefixexp():
            prefixexp = exp.prefixexp()
            if prefixexp.functioncall():
                func_call = prefixexp.functioncall()
                func_name = self._extract_function_name(func_call)

                # Check if this is a chained method call (e.g., Agent('name').turn())
                # Chained calls have structure: func_name args . method_name args
                # Simple declarations have: func_name args or func_name table
                # If there are more than 2 children, it's a chained call, not a declaration
                is_chained_call = func_call.getChildCount() > 2

                if func_name == "Agent" and not is_chained_call:
                    # Extract config from Agent {...}
                    config = self._extract_single_table_arg(func_call)
                    # Filter out None values from tools list (variable refs can't be resolved)
                    if config and "tools" in config:
                        tools = config["tools"]
                        if isinstance(tools, list):
                            config["tools"] = [t for t in tools if t is not None]
                    self.builder.register_agent(var_name, config if config else {}, None)
                elif func_name == "Tool":
                    # Extract config from Tool {...}
                    config = self._extract_single_table_arg(func_call)
                    if (
                        config
                        and isinstance(config, dict)
                        and isinstance(config.get("name"), str)
                        and config.get("name") != var_name
                    ):
                        self.errors.append(
                            ValidationMessage(
                                level="error",
                                message=(
                                    f"Tool name mismatch: '{var_name} = Tool {{ name = \"{config.get('name')}\" }}'. "
                                    f"Remove the 'name' field or set it to '{var_name}'."
                                ),
                                location=(self.current_line, self.current_col),
                                declaration="Tool",
                            )
                        )
                    self.builder.register_tool(var_name, config if config else {}, None)
                elif func_name == "Toolset":
                    # Extract config from Toolset {...}
                    config = self._extract_single_table_arg(func_call)
                    self.builder.register_toolset(var_name, config if config else {})
                elif func_name == "Procedure":
                    # New assignment syntax: main = Procedure { function(input) ... }
                    # Register as a named procedure
                    self.builder.register_named_procedure(
                        var_name,
                        None,  # Function not available during validation
                        {},  # Input schema will be extracted from top-level input {}
                        {},  # Output schema will be extracted from top-level output {}
                        {},  # State schema
                    )

    def _extract_single_table_arg(self, func_call) -> dict:
        """Extract a single table argument from a function call like Agent {...}."""
        args_list = func_call.args()
        if not args_list:
            return {}

        # Process first args entry only
        if len(args_list) > 0:
            args_ctx = args_list[0]
            if args_ctx.tableconstructor():
                return self._parse_table_constructor(args_ctx.tableconstructor())

        return {}

    def visitFunctioncall(self, ctx: LuaParser.FunctioncallContext):
        """Recognize and process DSL function calls."""
        try:
            # Extract line/column for error reporting
            if ctx.start:
                self.current_line = ctx.start.line
                self.current_col = ctx.start.column

            # Check for deprecated method calls like .turn() or .run()
            self._check_deprecated_method_calls(ctx)

            func_name = self._extract_function_name(ctx)

            # Check if this is a method call (e.g., Tool.called()) vs a direct call (e.g., Tool())
            # For "Tool.called()", parser extracts "Tool" as func_name but full text is "Tool.called(...)"
            # We want to skip if full_text shows it's actually calling a method ON Tool, not Tool itself
            full_text = ctx.getText()
            is_method_call = False
            if func_name:
                # If the text is "Tool.called(...)" and func_name is "Tool",
                # then it's actually calling .called() method on Tool, not calling Tool()
                # Check: does full_text have func_name followed by a dot/colon (not by opening paren)?
                # Pattern: func_name followed by . or : means it's accessing a method/property
                import re

                # Match: funcName followed by . or : (not by opening paren directly)
                method_access_pattern = re.escape(func_name) + r"[.:]"
                if re.search(method_access_pattern, full_text):
                    is_method_call = True

            if func_name in self.DSL_FUNCTIONS and not is_method_call:
                # Process the DSL call (but skip method calls like Tool.called())
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

    def _check_deprecated_method_calls(self, ctx: LuaParser.FunctioncallContext):
        """Check for deprecated method calls like .turn() or .run()."""
        # Method calls have the form: varOrExp nameAndArgs+
        # The nameAndArgs contains ':' NAME args for method calls
        # We need to check if any nameAndArgs contains 'turn' or 'run'

        # Get the full text of the function call
        full_text = ctx.getText()

        # Check for .turn() pattern (method call with dot notation)
        if ".turn(" in full_text or ":turn(" in full_text:
            self.errors.append(
                ValidationMessage(
                    level="error",
                    message='The .turn() method is deprecated. Use callable syntax instead: agent() or agent({message = "..."})',
                    location=(self.current_line, self.current_col),
                    declaration="Agent.turn",
                )
            )

        # Check for .run() pattern on agents
        if ".run(" in full_text or ":run(" in full_text:
            # Try to determine if this is an agent call (not procedure or other types)
            # If the text contains "Agent(" it's likely an agent method
            if "Agent(" in full_text or ctx.getText().startswith("agent"):
                self.errors.append(
                    ValidationMessage(
                        level="error",
                        message='The .run() method on agents is deprecated. Use callable syntax instead: agent() or agent({message = "..."})',
                        location=(self.current_line, self.current_col),
                        declaration="Agent.run",
                    )
                )

    def _extract_literal_value(self, exp):
        """Extract a literal value from an expression node."""
        if not exp:
            return None

        # Check for string literals
        if exp.string():
            string_ctx = exp.string()
            # Extract the string value (remove quotes)
            if string_ctx.NORMALSTRING():
                text = string_ctx.NORMALSTRING().getText()
                # Remove surrounding quotes
                if text.startswith('"') and text.endswith('"'):
                    return text[1:-1]
                elif text.startswith("'") and text.endswith("'"):
                    return text[1:-1]
            elif string_ctx.CHARSTRING():
                text = string_ctx.CHARSTRING().getText()
                # Remove surrounding quotes
                if text.startswith('"') and text.endswith('"'):
                    return text[1:-1]
                elif text.startswith("'") and text.endswith("'"):
                    return text[1:-1]

        # Check for number literals
        if exp.number():
            number_ctx = exp.number()
            if number_ctx.INT():
                return int(number_ctx.INT().getText())
            elif number_ctx.FLOAT():
                return float(number_ctx.FLOAT().getText())

        # Check for boolean literals
        if exp.getText() == "true":
            return True
        elif exp.getText() == "false":
            return False

        # Check for nil
        if exp.getText() == "nil":
            return None

        # Default to the text representation
        return exp.getText()

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
        elif func_name == "Agent":  # CamelCase only
            # Skip Agent calls inside function bodies - they're runtime lookups, not declarations
            if self.in_function_body:
                return self.visitChildren(ctx)

            if args and len(args) >= 1:  # Support curried syntax with just name
                agent_name = args[0]
                # Check if this is a declaration (has config) or a lookup (just name)
                if len(args) >= 2 and isinstance(args[1], dict):
                    # DEPRECATED: Curried syntax Agent "name" { config }
                    # Raise validation error
                    self.errors.append(
                        ValidationMessage(
                            level="error",
                            message=f'Curried syntax Agent "{agent_name}" {{...}} is deprecated. Use assignment syntax: {agent_name} = Agent {{...}}',
                            location=(self.current_line, self.current_col),
                            declaration="Agent",
                        )
                    )
                elif len(args) == 1 and isinstance(agent_name, str):
                    # DEPRECATED: Agent("name") lookup or curried declaration
                    # This is now invalid - users should use variable references
                    self.errors.append(
                        ValidationMessage(
                            level="error",
                            message=f'Agent("{agent_name}") lookup syntax is deprecated. Declare the agent with assignment: {agent_name} = Agent {{...}}, then use {agent_name}() to call it.',
                            location=(self.current_line, self.current_col),
                            declaration="Agent",
                        )
                    )
        elif func_name == "Model":  # CamelCase only
            if args and len(args) >= 1:
                # Check if this is assignment syntax (single dict arg) or curried syntax (name + dict)
                if len(args) == 1 and isinstance(args[0], dict):
                    # Assignment syntax: my_model = Model {config}
                    # Generate a temp name for validation
                    import uuid

                    temp_name = f"_temp_model_{uuid.uuid4().hex[:8]}"
                    self.builder.register_model(temp_name, args[0])
                elif len(args) >= 2 and isinstance(args[1], dict):
                    # Curried syntax: Model "name" {config}
                    config = args[1]
                    self.builder.register_model(args[0], config)
                elif isinstance(args[0], str):
                    # Just a name, register with empty config
                    self.builder.register_model(args[0], {})
        elif func_name == "Procedure":  # CamelCase only
            # Supports multiple syntax variants:
            # 1. Unnamed (new): Procedure { config with function }
            # 2. Named (curried): Procedure "name" { config }
            # 3. Named (old): procedure("name", {config}, function)
            # Note: args may contain None for unparseable expressions (like functions)
            if args and len(args) >= 1:
                # Check if first arg is a table (unnamed procedure syntax)
                # Tables are parsed as dict if they have named fields, or list if only positional
                if isinstance(args[0], dict):
                    # Unnamed syntax: Procedure {...} with named fields
                    # e.g., Procedure { output = {...}, function(input) ... end }
                    proc_name = "main"
                    config = args[0]
                elif isinstance(args[0], list):
                    # Unnamed syntax: Procedure {...} with only function (no named fields)
                    # e.g., Procedure { function(input) ... end }
                    # The list contains [None] for the unparseable function
                    proc_name = "main"
                    config = {}  # No extractable config from function-only table
                elif isinstance(args[0], str):
                    # Named syntax: Procedure "name" {...}
                    proc_name = args[0]
                    config = args[1] if len(args) >= 2 and isinstance(args[1], dict) else None
                else:
                    # Invalid syntax
                    return

                # Register that this named procedure exists (validation needs to know about 'main')
                # We use a stub/placeholder since the actual function will be registered at runtime
                self.builder.register_named_procedure(
                    proc_name,
                    None,  # Function not available during validation
                    {},  # Input schema extracted below
                    {},  # Output schema extracted below
                    {},  # State schema extracted below
                )

                # Extract schemas from config if available
                if config is not None and isinstance(config, dict):
                    # Extract inline input schema
                    if "input" in config and isinstance(config["input"], dict):
                        self.builder.register_input_schema(config["input"])

                    # Extract inline output schema
                    if "output" in config and isinstance(config["output"], dict):
                        self.builder.register_output_schema(config["output"])

                    # Extract inline state schema
                    if "state" in config and isinstance(config["state"], dict):
                        self.builder.register_state_schema(config["state"])
        elif func_name == "Prompt":  # CamelCase
            if args and len(args) >= 2:
                self.builder.register_prompt(args[0], args[1])
        elif func_name == "Hitl":  # CamelCase
            if args and len(args) >= 2:
                self.builder.register_hitl(args[0], args[1] if isinstance(args[1], dict) else {})
        elif func_name == "Stages":  # CamelCase
            if args:
                # Stages() can take multiple string arguments
                self.builder.set_stages(args)
        elif func_name == "Specification":  # CamelCase
            if args and len(args) >= 2:
                self.builder.register_specification(
                    args[0], args[1] if isinstance(args[1], list) else []
                )
        elif func_name == "Specifications":  # CamelCase
            # Specifications([[ Gherkin text ]])
            if args and len(args) >= 1:
                self.builder.register_specifications(args[0])
        elif func_name == "Step":  # CamelCase
            # Step("step text", function() ... end)
            if args and len(args) >= 2:
                self.builder.register_custom_step(args[0], args[1])
        elif func_name == "Evaluation":  # CamelCase
            # Evaluation({ runs = 10, parallel = true })
            if args and len(args) >= 1:
                self.builder.set_evaluation_config(args[0] if isinstance(args[0], dict) else {})
        elif func_name == "Evaluations":  # CamelCase
            # Evaluations({ dataset = {...}, evaluators = {...} })
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
        elif func_name == "input":
            # Top-level input schema for script mode: input { field1 = ..., field2 = ... }
            if args and len(args) >= 1 and isinstance(args[0], dict):
                self.builder.register_top_level_input(args[0])
        elif func_name == "output":
            # Top-level output schema for script mode: output { field1 = ..., field2 = ... }
            if args and len(args) >= 1 and isinstance(args[0], dict):
                self.builder.register_top_level_output(args[0])
        elif func_name == "Tool":  # CamelCase only
            # Curried syntax (Tool "name" {...} / Tool("name", ...)) is not supported.
            # Use assignment syntax: my_tool = Tool { ... }.
            if args and len(args) >= 1 and isinstance(args[0], str):
                tool_name = args[0]
                self.errors.append(
                    ValidationMessage(
                        level="error",
                        message=(
                            f'Curried Tool syntax is not supported: Tool "{tool_name}" {{...}}. '
                            f"Use assignment syntax: {tool_name} = Tool {{...}}."
                        ),
                        location=(self.current_line, self.current_col),
                        declaration="Tool",
                    )
                )
        elif func_name == "Toolset":  # CamelCase only
            # Toolset("name", {config})
            # or new curried syntax: Toolset "name" { config }
            if args and len(args) >= 1:  # Support curried syntax
                # First arg must be name (string)
                if isinstance(args[0], str):
                    toolset_name = args[0]
                    config = args[1] if len(args) >= 2 and isinstance(args[1], dict) else {}
                    # Register the toolset (validation only, no runtime impl yet)
                    self.builder.register_toolset(toolset_name, config)

    def _extract_arguments(self, ctx: LuaParser.FunctioncallContext) -> list:
        """Extract function arguments from parse tree.

        Returns a list where:
        - Parseable expressions are included as Python values
        - Unparseable expressions (like functions) are included as None placeholders
        This allows checking total argument count for validation.
        """
        args = []

        # functioncall has args() children
        # args: '(' explist? ')' | tableconstructor | LiteralString

        args_list = ctx.args()
        if not args_list:
            return args

        # Check if this is a method call chain by looking for '.' or ':' between args
        # For Agent("name").turn({...}), we should only extract "name"
        # For Procedure "name" {...}, we should extract both "name" and {...}
        is_method_chain = False
        if len(args_list) > 1:
            # Check if there's a method access between the first two args
            # Method chains have pattern: func(arg1).method(arg2)
            # Shorthand has pattern: func arg1 arg2

            # Look at the children of the functioncall context to see if there's
            # a '.' or ':' token between the first and second args
            found_first_args = False
            for i in range(ctx.getChildCount()):
                child = ctx.getChild(i)
                # Check if this is the first args
                if child == args_list[0]:
                    found_first_args = True
                elif found_first_args and child == args_list[1]:
                    # We've reached the second args without finding . or :
                    # So this is NOT a method chain
                    break
                elif found_first_args and hasattr(child, "symbol"):
                    # Check if this is a . or : token
                    token_text = child.getText()
                    if token_text in [".", ":"]:
                        is_method_chain = True
                        break

        # Process arguments
        if is_method_chain:
            # Only process first args for method chains like Agent("name").turn(...)
            args_to_process = [args_list[0]]
        else:
            # Process all args for shorthand syntax like Procedure "name" {...}
            args_to_process = args_list

        for args_ctx in args_to_process:
            # Check for different argument types
            if args_ctx.explist():
                # Regular function call with expression list
                explist = args_ctx.explist()
                for exp in explist.exp():
                    value = self._parse_expression(exp)
                    # Include None placeholders to preserve argument count
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

        # Detect field.<type>{...} builder syntax so we can preserve schema info
        prefix = ctx.prefixexp()
        if prefix and prefix.functioncall():
            func_ctx = prefix.functioncall()
            name_tokens = [t.getText() for t in func_ctx.NAME()]

            # field.string{required = true, ...}
            if len(name_tokens) >= 2 and name_tokens[0] == "field":
                field_type = name_tokens[-1]

                # Default field definition
                field_def = {"type": field_type, "required": False}

                # Parse options table if present
                if func_ctx.args():
                    # We only expect a single args() entry for the builder
                    first_arg = func_ctx.args(0)
                    if first_arg.tableconstructor():
                        options = self._parse_table_constructor(first_arg.tableconstructor())
                        if isinstance(options, dict):
                            field_def["required"] = bool(options.get("required", False))
                            if "default" in options and not field_def["required"]:
                                field_def["default"] = options["default"]
                            if "description" in options:
                                field_def["description"] = options["description"]
                            if "enum" in options:
                                field_def["enum"] = options["enum"]

                return field_def

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

                # Check for old type syntax in field definitions
                # Only check if this looks like a field definition (has type + required/description)
                if (
                    key == "type"
                    and isinstance(value, str)
                    and value in ["string", "number", "boolean", "integer", "array", "object"]
                ):
                    # Check if the parent table also has 'required' or 'description' keys
                    # which would indicate this is a field definition, not a JSON schema or evaluator config
                    parent_text = ctx.getText() if ctx else ""
                    # Skip if this is part of JSON schema or evaluator configuration
                    if (
                        "json_schema" not in parent_text
                        and "evaluators" not in parent_text
                        and "properties" not in parent_text  # JSON schema has 'properties'
                        and ("required=" in parent_text or "description=" in parent_text)
                    ):
                        self.errors.append(
                            ValidationMessage(
                                level="error",
                                message=f"Old type syntax detected. Use field.{value}{{}} instead of {{type = '{value}'}}",
                                line=field.start.line if field.start else 0,
                                column=field.start.column if field.start else 0,
                            )
                        )

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
