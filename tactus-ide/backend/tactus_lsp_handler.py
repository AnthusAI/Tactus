"""
Tactus-specific LSP handler.

Provides language intelligence features using the ANTLR-based validator.
Assumes syntax is already validated client-side by TypeScript parser.
"""

import logging
from typing import Dict, Any, List, Optional
from tactus.validation.validator import TactusValidator, ValidationMode
from tactus.core.registry import ValidationMessage

logger = logging.getLogger(__name__)


class TactusLSPHandler:
    """
    LSP handler for Tactus DSL.

    Provides semantic language intelligence features using the ANTLR-based validator.
    Focuses on semantic validation since syntax is handled client-side.
    """

    def __init__(self):
        self.validator = TactusValidator()
        self.documents: Dict[str, str] = {}  # uri -> content
        self.registries: Dict[str, Any] = {}  # uri -> ProcedureRegistry

    def validate_document(self, uri: str, text: str) -> List[Dict[str, Any]]:
        """
        Validate document and return LSP diagnostics.

        Focuses on semantic validation:
        - Missing required fields
        - Cross-reference errors
        - Type mismatches
        - Duplicate declarations

        Args:
            uri: Document URI
            text: Document content

        Returns:
            List of LSP diagnostic objects
        """
        self.documents[uri] = text

        try:
            # Run full validation
            result = self.validator.validate(text, ValidationMode.FULL)

            # Store registry for completions/hover
            if result.registry:
                self.registries[uri] = result.registry

            # Convert to LSP diagnostics
            diagnostics = []
            for error in result.errors:
                diagnostic = self._convert_to_diagnostic(error, "Error")
                if diagnostic:
                    diagnostics.append(diagnostic)

            for warning in result.warnings:
                diagnostic = self._convert_to_diagnostic(warning, "Warning")
                if diagnostic:
                    diagnostics.append(diagnostic)

            return diagnostics
        except Exception as e:
            logger.error(f"Error validating document {uri}: {e}", exc_info=True)
            return []

    def get_completions(self, uri: str, position: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Get context-aware completions.

        Examples:
        - Suggest DSL functions: name(), agent(), procedure()
        - Suggest agent names when typing in procedure
        - Suggest parameter names in agent config
        - Suggest tool names from agent tools list

        Args:
            uri: Document URI
            position: Cursor position {line, character}

        Returns:
            List of LSP completion items
        """
        completions = []

        # Basic DSL function completions
        dsl_functions = [
            {
                "label": "name",
                "kind": 3,  # Function
                "insertTextFormat": 2,  # Snippet
                "documentation": "Define the procedure name",
            },
            {
                "label": "agent",
                "kind": 3,
                "insertText": 'agent("${1:agent_name}", {\n\tprovider = "${2:openai}",\n\tmodel = "${3:gpt-4o}",\n\tsystem_prompt = "${4:You are helpful}"\n})',
                "insertTextFormat": 2,
                "documentation": "Define an agent",
            },
            {
                "label": "parameter",
                "kind": 3,
                "insertText": 'parameter("${1:param_name}", {\n\ttype = "${2:string}",\n\trequired = ${3:true},\n\tdefault = "${4:default_value}"\n})',
                "insertTextFormat": 2,
                "documentation": "Define a parameter",
            },
            {
                "label": "output",
                "kind": 3,
                "insertText": 'output("${1:output_name}", {\n\ttype = "${2:string}",\n\trequired = ${3:true}\n})',
                "insertTextFormat": 2,
                "documentation": "Define an output field",
            },
            {
                "label": "procedure",
                "kind": 3,
                "insertText": "procedure(function()\n\t${1:-- Your code here}\n\treturn { success = true }\nend)",
                "insertTextFormat": 2,
                "documentation": "Define the procedure function",
            },
        ]

        completions.extend(dsl_functions)

        # Context-aware completions from registry
        if uri in self.registries:
            registry = self.registries[uri]

            # Add agent names as completions
            for agent_name in registry.agents.keys():
                completions.append(
                    {
                        "label": agent_name,
                        "kind": 6,  # Variable
                        "detail": "Agent",
                        "documentation": f"Agent: {agent_name}",
                    }
                )

        return completions

    def get_hover(self, uri: str, position: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Get hover information.

        Examples:
        - Hover over agent name: show full configuration
        - Hover over parameter: show type and default
        - Hover over output: show field definition

        Args:
            uri: Document URI
            position: Cursor position {line, character}

        Returns:
            LSP hover object or None
        """
        if uri not in self.registries:
            return None

        registry = self.registries[uri]

        # For now, return general procedure info
        # TODO: Parse position to determine what's under cursor

        info_parts = []

        if registry.agents:
            info_parts.append(f"\n**Agents ({len(registry.agents)}):**")
            for agent_name, agent_decl in registry.agents.items():
                info_parts.append(f"- `{agent_name}`: {agent_decl.provider}/{agent_decl.model}")

        if registry.parameters:
            info_parts.append(f"\n**Parameters ({len(registry.parameters)}):**")
            for param_name, param_decl in registry.parameters.items():
                default = f" (default: {param_decl.default})" if param_decl.default else ""
                info_parts.append(f"- `{param_name}`: {param_decl.parameter_type.value}{default}")

        if registry.outputs:
            info_parts.append(f"\n**Outputs ({len(registry.outputs)}):**")
            for output_name, output_decl in registry.outputs.items():
                req = "required" if output_decl.required else "optional"
                info_parts.append(f"- `{output_name}`: {output_decl.field_type.value} ({req})")

        if info_parts:
            return {"contents": {"kind": "markdown", "value": "\n".join(info_parts)}}

        return None

    def get_signature_help(self, uri: str, position: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Get signature help for DSL functions.

        Examples:
        - agent(name, config) - show expected config fields
        - parameter(name, config) - show type, required, default

        Args:
            uri: Document URI
            position: Cursor position {line, character}

        Returns:
            LSP signature help object or None
        """
        # Basic signature help for DSL functions
        signatures = [
            {
                "label": "agent(name: string, config: table)",
                "documentation": "Define an agent with provider, model, and system_prompt",
                "parameters": [
                    {"label": "name", "documentation": "Agent name"},
                    {
                        "label": "config",
                        "documentation": "Agent configuration: {provider, model, system_prompt, tools}",
                    },
                ],
            },
            {
                "label": "parameter(name: string, config: table)",
                "documentation": "Define a parameter with type, required, and default",
                "parameters": [
                    {"label": "name", "documentation": "Parameter name"},
                    {
                        "label": "config",
                        "documentation": "Parameter configuration: {type, required, default, description}",
                    },
                ],
            },
            {
                "label": "output(name: string, config: table)",
                "documentation": "Define an output field with type and required",
                "parameters": [
                    {"label": "name", "documentation": "Output field name"},
                    {
                        "label": "config",
                        "documentation": "Output configuration: {type, required, description}",
                    },
                ],
            },
        ]

        return {"signatures": signatures, "activeSignature": 0, "activeParameter": 0}

    def close_document(self, uri: str):
        """Clean up when document is closed."""
        self.documents.pop(uri, None)
        self.registries.pop(uri, None)

    def _convert_to_diagnostic(
        self, message: ValidationMessage, severity_str: str
    ) -> Optional[Dict[str, Any]]:
        """
        Convert ValidationMessage to LSP diagnostic.

        Args:
            message: Tactus validation message
            severity_str: "Error" or "Warning"

        Returns:
            LSP diagnostic object
        """
        # LSP severity: 1=Error, 2=Warning, 3=Information, 4=Hint
        severity_map = {"Error": 1, "Warning": 2, "Information": 3, "Hint": 4}

        severity = severity_map.get(severity_str, 1)

        # Get location (line, column)
        if message.location:
            line, col = message.location
            # LSP uses 0-based line numbers
            line = max(0, line - 1)
            col = max(0, col - 1)
        else:
            line, col = 0, 0

        return {
            "range": {
                "start": {"line": line, "character": col},
                "end": {"line": line, "character": col + 10},  # Approximate end
            },
            "severity": severity,
            "source": "tactus-lsp",
            "message": message.message,
        }
