"""
Semantic visitor for Tactus DSL.

Walks the ANTLR parse tree and recognizes DSL patterns,
extracting declarations without executing code.
"""

import logging
import re
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
        "Task",  # CamelCase
        "IncludeTasks",  # CamelCase
        "Prompt",  # CamelCase
        "Hitl",  # CamelCase
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
        self.errors: list[ValidationMessage] = []
        self.warnings: list[ValidationMessage] = []
        self.current_line = 0
        self.current_col = 0
        self.in_function_body = False  # Track if we're inside a function body
        self._processed_task_calls: set[int] = set()
        self._retriever_aliases: dict[str, str] = {}
        self._retriever_modules: dict[str, str] = {}

    def _record_error(
        self,
        message: str,
        declaration: Optional[str] = None,
        line_number: Optional[int] = None,
        column_number: Optional[int] = None,
    ) -> None:
        """Record a validation error with the current location by default."""
        self.errors.append(
            ValidationMessage(
                level="error",
                message=message,
                location=(
                    self.current_line if line_number is None else line_number,
                    self.current_col if column_number is None else column_number,
                ),
                declaration=declaration,
            )
        )

    def visitFunctiondef(self, context):
        """Track when entering/exiting function definitions."""
        # Set flag when entering function body
        previous_in_function_body = self.in_function_body
        self.in_function_body = True
        try:
            child_visit_result = super().visitChildren(context)
        finally:
            # Restore previous state when exiting
            self.in_function_body = previous_in_function_body
        return child_visit_result

    def visitChunk(self, context: LuaParser.ChunkContext):
        """Enforce IncludeTasks file task-only constraint when used."""
        result = self.visitChildren(context)
        if self.builder.registry.include_tasks:
            # If any non-task declarations exist, error out.
            if (
                self.builder.registry.agents
                or self.builder.registry.toolsets
                or self.builder.registry.lua_tools
                or self.builder.registry.contexts
                or self.builder.registry.corpora
                or self.builder.registry.retrievers
                or self.builder.registry.compactors
                or self.builder.registry.named_procedures
            ):
                self._record_error(
                    "IncludeTasks files must only contain Task declarations.",
                    declaration="IncludeTasks",
                )
        return result

    def visitStat(self, context: LuaParser.StatContext):
        """Handle statement nodes including assignments."""
        # Check if this is an assignment statement
        if context.varlist() and context.explist():
            # This is an assignment: varlist '=' explist
            variable_list = context.varlist()
            expression_list = context.explist()

            # Get the variable name
            if variable_list.var() and len(variable_list.var()) > 0:
                assignment_target_node = variable_list.var()[0]
                if assignment_target_node.NAME():
                    assignment_target_name = assignment_target_node.NAME().getText()
                    self._track_retriever_alias(assignment_target_name, expression_list)

                    if not self._apply_setting_assignment(assignment_target_name, expression_list):
                        first_expression = self._extract_first_expression(expression_list)
                        if first_expression:
                            self._check_assignment_based_declaration(
                                assignment_target_name, first_expression
                            )

        attname_list = getattr(context, "attnamelist", None)
        exp_list = getattr(context, "explist", None)
        if callable(attname_list) and callable(exp_list):
            attname_nodes = attname_list()
            exp_nodes = exp_list()
            if attname_nodes and exp_nodes:
                name_nodes = attname_nodes.NAME()
                if name_nodes:
                    self._track_retriever_alias(name_nodes[0].getText(), exp_nodes)

        # Continue visiting children
        return self.visitChildren(context)

    def _check_assignment_based_declaration(
        self, assignment_target_name: str, assignment_expression
    ):
        """Check if an assignment is a DSL declaration like 'greeter = Agent {...}'."""
        # Look for prefixexp with functioncall pattern: Agent {...}
        if assignment_expression.prefixexp():
            prefix_expression = assignment_expression.prefixexp()
            if prefix_expression.functioncall():
                function_call = prefix_expression.functioncall()
                function_name = self._extract_function_name(function_call)
                dotted_name = None
                if function_name not in {
                    "Agent",
                    "Tool",
                    "Toolset",
                    "Context",
                    "Corpus",
                    "Retriever",
                    "Compactor",
                }:
                    dotted_name = self._extract_dotted_dsl_name(function_call)
                    if dotted_name:
                        function_name = dotted_name
                else:
                    dotted_name = self._extract_dotted_dsl_name(function_call)

                # Check if this is a chained method call (e.g., Agent('name').turn()).
                # Dotted module calls like vector.Corpus { ... } are not chained.
                get_text = getattr(function_call, "getText", None)
                function_call_text = get_text() if callable(get_text) else ""
                is_chained_method_call = (
                    re.search(r"[)}\\]]\\s*\\.", function_call_text) is not None
                )

                if function_name in {"Corpus", "Retriever"}:
                    has_namespace = dotted_name is not None or re.match(
                        r"[A-Za-z_][A-Za-z0-9_]*\\.", function_call_text
                    )
                    if not has_namespace:
                        self._record_error(
                            message=(
                                f"Direct {function_name} declarations are not supported. "
                                "Use module.Corpus { ... } instead."
                            ),
                            declaration=function_name,
                        )
                        return

                if function_name == "Agent" and is_chained_method_call:
                    return
                handled = self._register_assignment_based_declaration(
                    assignment_target_name, function_name, function_call
                )
                if handled:
                    return
                declaration_config = self._extract_single_table_arg(function_call)
                if isinstance(declaration_config, dict) and "corpus" in declaration_config:
                    retriever_id = self._resolve_retriever_id_from_call(function_call)
                    if retriever_id and "retriever_id" not in declaration_config:
                        declaration_config["retriever_id"] = retriever_id
                    self.builder.register_retriever(
                        assignment_target_name,
                        declaration_config,
                    )

    def _apply_setting_assignment(self, assignment_target_name: str, expression_list) -> bool:
        setting_handlers_by_name = {
            "default_provider": self.builder.set_default_provider,
            "default_model": self.builder.set_default_model,
            "return_prompt": self.builder.set_return_prompt,
            "error_prompt": self.builder.set_error_prompt,
            "status_prompt": self.builder.set_status_prompt,
            "async": self.builder.set_async,
            "max_depth": self.builder.set_max_depth,
            "max_turns": self.builder.set_max_turns,
        }
        if assignment_target_name not in setting_handlers_by_name:
            return False
        first_expression = self._extract_first_expression(expression_list)
        if not first_expression:
            return True
        literal_value = self._extract_literal_value(first_expression)
        setting_handlers_by_name[assignment_target_name](literal_value)
        return True

    def _extract_first_expression(self, expression_list):
        exp_list = getattr(expression_list, "exp", None)
        if not callable(exp_list):
            return None
        expressions = exp_list()
        if expressions:
            return expressions[0]
        return None

    def _register_assignment_based_declaration(
        self,
        assignment_target_name: str,
        function_name: str,
        function_call,
    ) -> bool:
        declaration_config = self._extract_single_table_arg(function_call)
        normalized_config = declaration_config if declaration_config else {}
        if function_name == "Agent":
            if "tools" in normalized_config:
                tool_name_list = normalized_config["tools"]
                if isinstance(tool_name_list, list):
                    normalized_config["tools"] = [
                        tool_name for tool_name in tool_name_list if tool_name is not None
                    ]
            self.builder.register_agent(assignment_target_name, normalized_config, None)
            return True
        if function_name == "Tool":
            if (
                isinstance(normalized_config, dict)
                and isinstance(normalized_config.get("name"), str)
                and normalized_config.get("name") != assignment_target_name
            ):
                self._record_error(
                    message=(
                        f"Tool name mismatch: '{assignment_target_name} = Tool {{ name = \"{normalized_config.get('name')}\" }}'. "
                        f"Remove the 'name' field or set it to '{assignment_target_name}'."
                    ),
                    declaration="Tool",
                )
            self.builder.register_tool(assignment_target_name, normalized_config, None)
            return True
        if function_name == "Toolset":
            self.builder.register_toolset(assignment_target_name, normalized_config)
            return True
        if function_name == "Context":
            self.builder.register_context(assignment_target_name, normalized_config)
            return True
        if function_name == "Corpus":
            self.builder.register_corpus(assignment_target_name, normalized_config)
            return True
        if function_name == "Retriever":
            retriever_id = self._resolve_retriever_id_from_call(function_call)
            if retriever_id and "retriever_id" not in normalized_config:
                normalized_config["retriever_id"] = retriever_id
            self.builder.register_retriever(assignment_target_name, normalized_config)
            return True
        if function_name == "Compactor":
            self.builder.register_compactor(assignment_target_name, normalized_config)
            return True
        if function_name == "Procedure":
            self.builder.register_named_procedure(
                assignment_target_name,
                None,
                {},
                {},
                {},
            )
            return True
        if function_name == "Task":
            self._processed_task_calls.add(id(function_call))
            self._register_task_declaration(assignment_target_name, function_call)
            return True
        return False

    def _extract_single_table_arg(self, function_call) -> dict:
        """Extract a single table argument from a function call like Agent {...}."""
        args_method = getattr(function_call, "args", None)
        if args_method is None:
            return {}

        argument_list_nodes = args_method()
        if not argument_list_nodes:
            return {}

        # Process first args entry only
        argument_context = argument_list_nodes[0]
        if argument_context.tableconstructor():
            return self._parse_table_constructor(argument_context.tableconstructor())

        return {}

    def visitFunctioncall(self, context: LuaParser.FunctioncallContext):
        """Recognize and process DSL function calls."""
        try:
            # Extract line/column for error reporting
            if context.start:
                self.current_line = context.start.line
                self.current_col = context.start.column

            # Check for deprecated method calls like .turn() or .run()
            self._check_deprecated_method_calls(context)

            function_name = self._extract_function_name(context)

            # Check if this is a method call (e.g., Tool.called()) vs a direct call (e.g., Tool())
            # For "Tool.called()", parser extracts "Tool" as func_name but full text is "Tool.called(...)"
            # We want to skip if full_text shows it's actually calling a method ON Tool, not Tool itself
            is_method_access_call = self._is_method_access_call(function_name, context)

            if function_name in self.DSL_FUNCTIONS and not is_method_access_call:
                # Process the DSL call (but skip method calls like Tool.called())
                try:
                    if function_name == "Task":
                        if id(context) in self._processed_task_calls:
                            return None
                        self._register_task_declaration(None, context)
                        return None
                    if function_name == "IncludeTasks":
                        self._register_include_tasks(context)
                        return None
                    self._process_dsl_call(function_name, context)
                except Exception as processing_exception:
                    self.errors.append(
                        ValidationMessage(
                            level="error",
                            message=(f"Error processing {function_name}: {processing_exception}"),
                            location=(self.current_line, self.current_col),
                            declaration=function_name,
                        )
                    )
        except Exception as visit_exception:
            logger.debug("Error in visitFunctioncall: %s", visit_exception)

        return self.visitChildren(context)

    def _register_task_declaration(
        self,
        assignment_name: Optional[str],
        function_call_context: LuaParser.FunctioncallContext,
        parent_task: Optional[str] = None,
    ) -> None:
        args = self._extract_arguments(function_call_context)
        task_name = None
        task_config: dict[str, Any] = {}

        if args:
            if isinstance(args[0], str):
                task_name = args[0]
            elif isinstance(args[0], dict):
                task_config = args[0]

        if len(args) >= 2 and isinstance(args[1], dict):
            task_config = args[1]

        if assignment_name and task_name and assignment_name != task_name:
            self._record_error(
                message=(
                    f"Task name mismatch: '{assignment_name} = Task \"{task_name}\" {{ ... }}'. "
                    f"Remove the string name or set it to '{assignment_name}'."
                ),
                declaration="Task",
            )
            task_name = assignment_name

        if assignment_name and not task_name:
            task_name = assignment_name

        if not task_name:
            self._record_error("Task name is required.", declaration="Task")
            return

        children = self._extract_nested_tasks(function_call_context)
        for child in children:
            child_name = child["name"]
            self.builder.register_task(child_name, child.get("config", {}), parent=task_name)

        self.builder.register_task(task_name, task_config, parent=parent_task)

    def _extract_nested_tasks(
        self, function_call_context: LuaParser.FunctioncallContext
    ) -> list[dict[str, Any]]:
        """Extract nested Task calls from a Task { ... } table constructor."""
        nested_tasks: list[dict[str, Any]] = []
        argument_list_nodes = function_call_context.args()
        if not argument_list_nodes:
            return nested_tasks

        for args_ctx in argument_list_nodes:
            table_ctx = args_ctx.tableconstructor()
            if not table_ctx or not table_ctx.fieldlist():
                continue
            for field in table_ctx.fieldlist().field():
                if len(field.exp()) != 1:
                    continue
                child_exp = field.exp(0)
                child_call = None
                if hasattr(child_exp, "functioncall") and child_exp.functioncall():
                    child_call = child_exp.functioncall()
                elif child_exp.prefixexp() and child_exp.prefixexp().functioncall():
                    child_call = child_exp.prefixexp().functioncall()
                if not child_call:
                    continue
                child_name = self._extract_function_name(child_call)
                if child_name != "Task":
                    continue
                child_args = self._extract_arguments(child_call)
                child_task_name = None
                if field.NAME():
                    child_task_name = field.NAME().getText()
                if not child_task_name and child_args:
                    child_task_name = child_args[0] if isinstance(child_args[0], str) else None
                child_task_config = {}
                if len(child_args) >= 2 and isinstance(child_args[1], dict):
                    child_task_config = child_args[1]
                if field.NAME() and child_args and isinstance(child_args[0], str):
                    if field.NAME().getText() != child_args[0]:
                        self._record_error(
                            message=(
                                f"Task name mismatch: '{field.NAME().getText()} = Task \"{child_args[0]}\" {{ ... }}'. "
                                f"Remove the string name or set it to '{field.NAME().getText()}'."
                            ),
                            declaration="Task",
                        )
                if child_task_name:
                    nested_tasks.append(
                        {
                            "name": child_task_name,
                            "config": child_task_config,
                        }
                    )
        return nested_tasks

    def _register_include_tasks(self, context: LuaParser.FunctioncallContext) -> None:
        args = self._extract_arguments(context)
        if not args:
            self._record_error("IncludeTasks requires a path string.", declaration="IncludeTasks")
            return
        if not isinstance(args[0], str):
            self._record_error(
                "IncludeTasks path must be a string literal.",
                declaration="IncludeTasks",
            )
            return
        namespace = None
        if len(args) >= 2:
            if isinstance(args[1], str):
                namespace = args[1]
            elif isinstance(args[1], dict):
                namespace = args[1].get("namespace")
        self.builder.register_include_tasks(args[0], namespace)

    def _check_deprecated_method_calls(self, ctx: LuaParser.FunctioncallContext):
        """Check for deprecated method calls like .turn() or .run()."""
        # Method calls have the form: varOrExp nameAndArgs+
        # The nameAndArgs contains ':' NAME args for method calls
        # We need to check if any nameAndArgs contains 'turn' or 'run'

        # Get the full text of the function call
        full_text = ctx.getText()

        # Check for .turn() pattern (method call with dot notation)
        if ".turn(" in full_text or ":turn(" in full_text:
            self._record_error(
                message=(
                    "The .turn() method is deprecated. Use callable syntax instead: "
                    'agent() or agent({message = "..."})'
                ),
                declaration="Agent.turn",
            )

        # Check for .run() pattern on agents
        if ".run(" in full_text or ":run(" in full_text:
            # Try to determine if this is an agent call (not procedure or other types)
            # If the text contains "Agent(" it's likely an agent method
            if "Agent(" in full_text or ctx.getText().startswith("agent"):
                self._record_error(
                    message=(
                        "The .run() method on agents is deprecated. Use callable syntax instead: "
                        'agent() or agent({message = "..."})'
                    ),
                    declaration="Agent.run",
                )

    def _is_method_access_call(
        self, function_name: Optional[str], ctx: LuaParser.FunctioncallContext
    ) -> bool:
        """Return True when the call is actually a method access like Tool.called()."""
        if not function_name:
            return False

        function_call_text = ctx.getText()
        method_access_pattern = re.escape(function_name) + r"[.:]"
        return re.search(method_access_pattern, function_call_text) is not None

    def _extract_literal_value(self, expression_node):
        """Extract a literal value from an expression node."""
        if not expression_node:
            return None

        expression_text = expression_node.getText()

        # Check for string literals
        if expression_node.string():
            string_context = expression_node.string()
            # Extract the string value (remove quotes)
            if string_context.NORMALSTRING():
                string_text = string_context.NORMALSTRING().getText()
                # Remove surrounding quotes
                if string_text.startswith('"') and string_text.endswith('"'):
                    return string_text[1:-1]
                elif string_text.startswith("'") and string_text.endswith("'"):
                    return string_text[1:-1]
            elif string_context.CHARSTRING():
                string_text = string_context.CHARSTRING().getText()
                # Character strings are always quoted in Lua tokens.
                if (
                    len(string_text) >= 2
                    and string_text[0] == string_text[-1]
                    and string_text[0] in ("'", '"')
                ):
                    return string_text[1:-1]
                return string_text

        # Check for number literals
        if expression_node.number():
            number_context = expression_node.number()
            if number_context.INT():
                return int(number_context.INT().getText())
            elif number_context.FLOAT():
                return float(number_context.FLOAT().getText())

        # Check for boolean literals
        if expression_text == "true":
            return True
        elif expression_text == "false":
            return False

        # Check for nil
        if expression_text == "nil":
            return None

        # Default to the text representation
        return expression_text

    def _extract_function_name(
        self, function_call_context: LuaParser.FunctioncallContext
    ) -> Optional[str]:
        """Extract function name from parse tree."""
        # The function name is the first child of functioncall
        # Look for a terminal node with text
        for i in range(function_call_context.getChildCount()):
            child = function_call_context.getChild(i)
            if hasattr(child, "symbol"):
                # It's a terminal node
                token_text = child.getText()
                if token_text and token_text.isidentifier():
                    return token_text

        # Fallback: try varOrExp approach
        if function_call_context.varOrExp():
            var_or_exp = function_call_context.varOrExp()
            # varOrExp: var | '(' exp ')'
            if var_or_exp.var():
                var_ctx = var_or_exp.var()
                # var: (NAME | '(' exp ')' varSuffix) varSuffix*
                if var_ctx.NAME():
                    return var_ctx.NAME().getText()

        return None

    def _extract_dotted_dsl_name(
        self, function_call_context: LuaParser.FunctioncallContext
    ) -> Optional[str]:
        """Extract DSL names from dotted calls like module.Corpus {...}."""
        get_text = getattr(function_call_context, "getText", None)
        if not callable(get_text):
            return None
        function_call_text = get_text()
        match = re.match(
            r"(?:[A-Za-z_][A-Za-z0-9_]*\.)+(Agent|Tool|Toolset|Context|Corpus|Retriever|Compactor)\b",
            function_call_text,
        )
        if match:
            return match.group(1)
        return None

    def _track_retriever_alias(self, assignment_name: str, expression_list) -> None:
        """Track retriever constructor aliases from require(...) assignments."""
        try:
            expressions = expression_list.exp()
        except Exception:
            return
        if not expressions:
            return
        expression_node = expressions[0]
        get_text = getattr(expression_node, "getText", None)
        if not callable(get_text):
            return
        expression_text = get_text()
        match = re.match(
            r'require\("tactus\.retrievers\.([A-Za-z0-9_]+)"\)(?:\.Retriever)?$',
            expression_text,
        )
        if not match:
            return
        module_name = match.group(1)
        retriever_id = module_name.replace("_", "-")
        if expression_text.endswith(".Retriever"):
            self._retriever_aliases[assignment_name] = retriever_id
        else:
            self._retriever_modules[assignment_name] = retriever_id

    def _resolve_retriever_id_from_call(
        self, function_call_context: LuaParser.FunctioncallContext
    ) -> Optional[str]:
        function_name = self._extract_function_name(function_call_context)
        if function_name and function_name in self._retriever_aliases:
            return self._retriever_aliases[function_name]
        call_text = function_call_context.getText()
        dotted_match = re.match(r"([A-Za-z_][A-Za-z0-9_]*)\.Retriever\b", call_text)
        if dotted_match:
            module_name = dotted_match.group(1)
            return self._retriever_modules.get(module_name)
        return None

    def _parse_functioncall_expression(
        self, function_call_context: LuaParser.FunctioncallContext
    ) -> Any:
        """Parse function calls used inside DSL expressions (e.g., context messages)."""
        function_name = self._extract_function_name(function_call_context)
        if not function_name:
            return None

        args = self._extract_arguments(function_call_context)

        if function_name == "template":
            template_text = args[0] if args else ""
            vars_dict = args[1] if len(args) > 1 else {}
            if not isinstance(template_text, str):
                return None
            if not isinstance(vars_dict, dict):
                vars_dict = {}
            return {"template": template_text, "vars": vars_dict}

        if function_name in {"system", "user", "assistant"}:
            if not args:
                return None
            arg = args[0]
            if isinstance(arg, dict) and "template" in arg:
                return {
                    "type": function_name,
                    "template": arg.get("template"),
                    "vars": arg.get("vars", {}),
                }
            if isinstance(arg, str):
                return {"type": function_name, "content": arg}
            return {"type": function_name, "content": str(arg)}

        if function_name == "context":
            if not args:
                return None
            pack_name = args[0]
            budget = args[1] if len(args) > 1 else None
            directive: dict[str, Any] = {
                "type": "context",
                "name": pack_name if isinstance(pack_name, str) else str(pack_name),
            }
            if isinstance(budget, dict):
                directive["budget"] = budget
            return directive

        if function_name == "history":
            return {"type": "history"}

        return None

    def _process_dsl_call(self, function_name: str, ctx: LuaParser.FunctioncallContext) -> None:
        """Extract arguments and register declaration."""
        argument_values = self._extract_arguments(ctx)

        if function_name == "name":
            if argument_values and len(argument_values) >= 1:
                self.builder.set_name(argument_values[0])
        elif function_name == "version":
            if argument_values and len(argument_values) >= 1:
                self.builder.set_version(argument_values[0])
        elif function_name == "Agent":  # CamelCase only
            # Skip Agent calls inside function bodies - they're runtime lookups, not declarations
            if self.in_function_body:
                self.visitChildren(ctx)
                return None

            if (
                argument_values and len(argument_values) >= 1
            ):  # Support curried syntax with just name
                agent_name = argument_values[0]
                # Check if this is a declaration (has config) or a lookup (just name)
                if len(argument_values) >= 2 and isinstance(argument_values[1], dict):
                    # DEPRECATED: Curried syntax Agent "name" { config }
                    # Raise validation error
                    self.errors.append(
                        ValidationMessage(
                            level="error",
                            message=(
                                f'Curried syntax Agent "{agent_name}" {{...}} is deprecated. '
                                f"Use assignment syntax: {agent_name} = Agent {{...}}"
                            ),
                            location=(self.current_line, self.current_col),
                            declaration="Agent",
                        )
                    )
                elif len(argument_values) == 1 and isinstance(agent_name, str):
                    # DEPRECATED: Agent("name") lookup or curried declaration
                    # This is now invalid - users should use variable references
                    self._record_error(
                        message=(
                            f'Agent("{agent_name}") lookup syntax is deprecated. '
                            f"Declare the agent with assignment: {agent_name} = Agent {{...}}, "
                            f"then use {agent_name}() to call it."
                        ),
                        declaration="Agent",
                    )
        elif function_name == "Model":  # CamelCase only
            # Skip Model calls inside function bodies - they're runtime lookups, not declarations
            if self.in_function_body:
                self.visitChildren(ctx)
                return None
            if argument_values and len(argument_values) >= 1:
                # Check if this is assignment syntax (single dict arg) or curried syntax (name + dict)
                if len(argument_values) == 1 and isinstance(argument_values[0], dict):
                    # Assignment syntax: my_model = Model {config}
                    # Generate a temp name for validation
                    import uuid

                    temp_name = f"_temp_model_{uuid.uuid4().hex[:8]}"
                    self.builder.register_model(temp_name, argument_values[0])
                elif len(argument_values) >= 2 and isinstance(argument_values[1], dict):
                    # Curried syntax: Model "name" {config}
                    config = argument_values[1]
                    self.builder.register_model(argument_values[0], config)
                elif isinstance(argument_values[0], str):
                    # Just a name, register with empty config
                    self.builder.register_model(argument_values[0], {})
        elif function_name == "Procedure":  # CamelCase only
            # Supports multiple syntax variants:
            # 1. Unnamed (new): Procedure { config with function }
            # 2. Named (curried): Procedure "name" { config }
            # 3. Named (old): procedure("name", {config}, function)
            # Note: args may contain None for unparseable expressions (like functions)
            if argument_values and len(argument_values) >= 1:
                # Check if first arg is a table (unnamed procedure syntax)
                # Tables are parsed as dict if they have named fields, or list if only positional
                if isinstance(argument_values[0], dict):
                    # Unnamed syntax: Procedure {...} with named fields
                    # e.g., Procedure { output = {...}, function(input) ... end }
                    proc_name = "main"
                    config = argument_values[0]
                elif isinstance(argument_values[0], list):
                    # Unnamed syntax: Procedure {...} with only function (no named fields)
                    # e.g., Procedure { function(input) ... end }
                    # The list contains [None] for the unparseable function
                    proc_name = "main"
                    config = {}  # No extractable config from function-only table
                elif isinstance(argument_values[0], str):
                    # Named syntax: Procedure "name" {...}
                    proc_name = argument_values[0]
                    config = (
                        argument_values[1]
                        if len(argument_values) >= 2 and isinstance(argument_values[1], dict)
                        else None
                    )
                else:
                    # Invalid syntax
                    return None

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
        elif function_name == "Prompt":  # CamelCase
            if argument_values and len(argument_values) >= 2:
                self.builder.register_prompt(argument_values[0], argument_values[1])
        elif function_name == "Hitl":  # CamelCase
            if argument_values and len(argument_values) >= 2:
                self.builder.register_hitl(
                    argument_values[0],
                    argument_values[1] if isinstance(argument_values[1], dict) else {},
                )
        elif function_name == "Specification":  # CamelCase
            # Three supported forms:
            # - Specification([[ Gherkin text ]]) (inline Gherkin)
            # - Specification("name", { ... })   (structured form; legacy)
            # - Specification { from = "path" }  (external file reference)
            if argument_values and len(argument_values) == 1:
                specification_argument = argument_values[0]
                if isinstance(specification_argument, dict) and "from" in specification_argument:
                    # External file reference
                    self.builder.register_specs_from(specification_argument["from"])
                else:
                    # Inline Gherkin text
                    self.builder.register_specifications(specification_argument)
            elif argument_values and len(argument_values) >= 2:
                self.builder.register_specification(
                    argument_values[0],
                    argument_values[1] if isinstance(argument_values[1], list) else [],
                )
        elif function_name == "Specifications":  # CamelCase
            # Specifications([[ Gherkin text ]]) (plural form; singular is Specification([[...]]))
            if argument_values and len(argument_values) >= 1:
                self.builder.register_specifications(argument_values[0])
        elif function_name == "Step":  # CamelCase
            # Step("step text", function() ... end)
            if argument_values and len(argument_values) >= 2:
                self.builder.register_custom_step(argument_values[0], argument_values[1])
        elif function_name == "Evaluation":  # CamelCase
            # Either:
            # - Evaluation({ runs = 10, parallel = true })               (simple config)
            # - Evaluation({ dataset = {...}, evaluators = {...}, ... }) (alias for Evaluations)
            if (
                argument_values
                and len(argument_values) >= 1
                and isinstance(argument_values[0], dict)
            ):
                evaluation_config = argument_values[0]
                if any(
                    key in evaluation_config
                    for key in ("dataset", "dataset_file", "evaluators", "thresholds")
                ):
                    self.builder.register_evaluations(evaluation_config)
                else:
                    self.builder.set_evaluation_config(evaluation_config)
            elif argument_values and len(argument_values) >= 1:
                self.builder.set_evaluation_config({})
        elif function_name == "Evaluations":  # CamelCase
            # Evaluation(s)({ dataset = {...}, evaluators = {...} })
            if argument_values and len(argument_values) >= 1:
                self.builder.register_evaluations(
                    argument_values[0] if isinstance(argument_values[0], dict) else {}
                )
        elif function_name == "default_provider":
            if argument_values and len(argument_values) >= 1:
                self.builder.set_default_provider(argument_values[0])
        elif function_name == "default_model":
            if argument_values and len(argument_values) >= 1:
                self.builder.set_default_model(argument_values[0])
        elif function_name == "return_prompt":
            if argument_values and len(argument_values) >= 1:
                self.builder.set_return_prompt(argument_values[0])
        elif function_name == "error_prompt":
            if argument_values and len(argument_values) >= 1:
                self.builder.set_error_prompt(argument_values[0])
        elif function_name == "status_prompt":
            if argument_values and len(argument_values) >= 1:
                self.builder.set_status_prompt(argument_values[0])
        elif function_name == "async":
            if argument_values and len(argument_values) >= 1:
                self.builder.set_async(argument_values[0])
        elif function_name == "max_depth":
            if argument_values and len(argument_values) >= 1:
                self.builder.set_max_depth(argument_values[0])
        elif function_name == "max_turns":
            if argument_values and len(argument_values) >= 1:
                self.builder.set_max_turns(argument_values[0])
        elif function_name == "input":
            # Top-level input schema for script mode: input { field1 = ..., field2 = ... }
            if (
                argument_values
                and len(argument_values) >= 1
                and isinstance(argument_values[0], dict)
            ):
                self.builder.register_top_level_input(argument_values[0])
        elif function_name == "output":
            # Top-level output schema for script mode: output { field1 = ..., field2 = ... }
            if (
                argument_values
                and len(argument_values) >= 1
                and isinstance(argument_values[0], dict)
            ):
                self.builder.register_top_level_output(argument_values[0])
        elif function_name == "Tool":  # CamelCase only
            # Curried syntax (Tool "name" {...} / Tool("name", ...)) is not supported.
            # Use assignment syntax: my_tool = Tool { ... }.
            if (
                argument_values
                and len(argument_values) >= 1
                and isinstance(argument_values[0], str)
            ):
                tool_name = argument_values[0]
                self._record_error(
                    message=(
                        f'Curried Tool syntax is not supported: Tool "{tool_name}" {{...}}. '
                        f"Use assignment syntax: {tool_name} = Tool {{...}}."
                    ),
                    declaration="Tool",
                )
        elif function_name == "Toolset":  # CamelCase only
            # Toolset("name", {config})
            # or new curried syntax: Toolset "name" { config }
            if argument_values and len(argument_values) >= 1:  # Support curried syntax
                # First arg must be name (string)
                if isinstance(argument_values[0], str):
                    toolset_name = argument_values[0]
                    config = (
                        argument_values[1]
                        if len(argument_values) >= 2 and isinstance(argument_values[1], dict)
                        else {}
                    )
                    # Register the toolset (validation only, no runtime impl yet)
                    self.builder.register_toolset(toolset_name, config)

        return None

    def _extract_arguments(self, ctx: LuaParser.FunctioncallContext) -> list:
        """Extract function arguments from parse tree.

        Returns a list where:
        - Parseable expressions are included as Python values
        - Unparseable expressions (like functions) are included as None placeholders
        This allows checking total argument count for validation.
        """
        parsed_arguments = []

        # functioncall has args() children
        # args: '(' explist? ')' | tableconstructor | LiteralString

        argument_nodes = ctx.args()
        if not argument_nodes:
            return parsed_arguments

        # Check if this is a method call chain by looking for '.' or ':' between args
        # For Agent("name").turn({...}), we should only extract "name"
        # For Procedure "name" {...}, we should extract both "name" and {...}
        is_method_chain = False
        if len(argument_nodes) > 1:
            # Check if there's a method access between the first two args
            # Method chains have pattern: func(arg1).method(arg2)
            # Shorthand has pattern: func arg1 arg2

            # Look at the children of the functioncall context to see if there's
            # a '.' or ':' token between the first and second args
            found_first_args = False
            for i in range(ctx.getChildCount()):
                child = ctx.getChild(i)
                # Check if this is the first args
                if child == argument_nodes[0]:
                    found_first_args = True
                elif found_first_args and child == argument_nodes[1]:
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
            args_to_process = [argument_nodes[0]]
        else:
            # Process all args for shorthand syntax like Procedure "name" {...}
            args_to_process = argument_nodes

        for args_ctx in args_to_process:
            # Check for different argument types
            if args_ctx.explist():
                # Regular function call with expression list
                expression_list = args_ctx.explist()
                for expression in expression_list.exp():
                    value = self._parse_expression(expression)
                    # Include None placeholders to preserve argument count
                    parsed_arguments.append(value)
            elif args_ctx.tableconstructor():
                # Table constructor argument
                table = self._parse_table_constructor(args_ctx.tableconstructor())
                parsed_arguments.append(table)
            elif args_ctx.string():
                # String literal argument
                string_val = self._parse_string(args_ctx.string())
                parsed_arguments.append(string_val)

        return parsed_arguments

    def _parse_expression(self, ctx: LuaParser.ExpContext) -> Any:
        """Parse an expression to a Python value."""
        if not ctx:
            return None

        # Detect field.<type>{...} builder syntax so we can preserve schema info
        prefix_expression = ctx.prefixexp()
        if prefix_expression and prefix_expression.functioncall():
            function_call_context = prefix_expression.functioncall()
            function_name_tokens = [token.getText() for token in function_call_context.NAME()]

            # field.string{required = true, ...}
            if len(function_name_tokens) >= 2 and function_name_tokens[0] == "field":
                field_type = function_name_tokens[-1]

                # Default field definition
                field_def = {"type": field_type, "required": False}

                # Parse options table if present
                if function_call_context.args():
                    # We only expect a single args() entry for the builder
                    first_arg = function_call_context.args(0)
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
        function_call = getattr(ctx, "functioncall", None)
        if callable(function_call):
            return self._parse_functioncall_expression(function_call())

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
        token_text = token.getText()

        # Handle different Lua string formats
        if token_text.startswith("[[") and token_text.endswith("]]"):
            # Long string literal
            return token_text[2:-2]
        elif token_text.startswith('"') and token_text.endswith('"'):
            # Double-quoted string
            return self._unescape_basic_string(token_text[1:-1], '"')
        elif token_text.startswith("'") and token_text.endswith("'"):
            # Single-quoted string
            return self._unescape_basic_string(token_text[1:-1], "'")

        return token_text

    def _unescape_basic_string(self, content: str, quote_char: str) -> str:
        content = content.replace("\\n", "\n")
        content = content.replace("\\t", "\t")
        if quote_char == '"':
            content = content.replace('\\"', '"')
        elif quote_char == "'":
            content = content.replace("\\'", "'")
        content = content.replace("\\\\", "\\")
        return content

    def _parse_table_constructor(self, ctx: LuaParser.TableconstructorContext) -> Any:
        """Parse Lua table constructor to Python dict."""
        parsed_table = {}
        array_items = []

        if not ctx or not ctx.fieldlist():
            # Empty table
            return []  # Return empty list for empty tables (matches runtime behavior)

        field_list = ctx.fieldlist()
        for field in field_list.field():
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
                                message=(
                                    f"Old type syntax detected. Use field.{value}{{}} instead of "
                                    f"{{type = '{value}'}}"
                                ),
                                line=field.start.line if field.start else 0,
                                column=field.start.column if field.start else 0,
                            )
                        )

                parsed_table[key] = value
            elif len(field.exp()) == 2:
                # Indexed field: '[' exp ']' '=' exp
                # Skip for now (complex)
                pass
            elif len(field.exp()) == 1:
                # Array element: exp
                value = self._parse_expression(field.exp(0))
                array_items.append(value)

        # If we only have array items, return as list
        if array_items and not parsed_table:
            return array_items

        # If we have both, prefer dict (shouldn't happen in DSL)
        if array_items:
            # Mixed table - add array items with numeric keys
            for i, item in enumerate(array_items, 1):
                parsed_table[i] = item

        return parsed_table if parsed_table else []

    def _parse_number(self, number_context: LuaParser.NumberContext) -> float:
        """Parse Lua number to Python number."""
        number_text = number_context.getText()

        # Try integer first
        try:
            return int(number_text)
        except ValueError:
            pass

        # Try float
        try:
            return float(number_text)
        except ValueError:
            pass

        # Try hex
        if number_text.startswith("0x") or number_text.startswith("0X"):
            try:
                return int(number_text, 16)
            except ValueError:
                pass

        return 0
