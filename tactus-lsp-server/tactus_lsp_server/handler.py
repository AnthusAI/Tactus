"""
Tactus LSP Handler - Core language intelligence features.

Transport-agnostic handler that provides:
- Document validation with diagnostics
- Code completions
- Hover information
- Signature help
- Semantic tokens (for semantic highlighting)
"""

import logging
from typing import Dict, Any, List, Optional
from tactus.validation.validator import TactusValidator, ValidationMode
from tactus.core.registry import ValidationMessage
from tactus_lsp_server.semantic_tokens import encode_semantic_tokens

# Use stderr for logging to avoid conflicting with stdio communication
logger = logging.getLogger(__name__)


class TactusLSPHandler:
    """
    LSP handler for Tactus DSL.

    Provides semantic language intelligence features using the ANTLR-based validator.
    Transport-agnostic - can be used with stdio, HTTP, or any other protocol.
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
        - Suggest DSL keywords: Agent, Procedure, Task, Tool
        - Suggest agent names from registry
        - Suggest field builders: field.string, field.number, etc.

        Args:
            uri: Document URI
            position: Cursor position {line, character}

        Returns:
            List of LSP completion items
        """
        completions = []

        # Basic DSL keywords completions
        dsl_keywords = [
            {
                "label": "Agent",
                "kind": 3,  # Function
                "insertText": "Agent {\n\tprovider = \"${1:openai}\",\n\tmodel = \"${2:gpt-4o}\",\n\tsystem_prompt = \"${3:You are helpful}\",\n\ttools = {${4:}}\n}",
                "insertTextFormat": 2,  # Snippet
                "documentation": "Define an LLM-powered agent",
            },
            {
                "label": "Procedure",
                "kind": 3,
                "insertText": "Procedure {\n\tinput = {\n\t\t${1:param} = field.string{required = true}\n\t},\n\toutput = {\n\t\t${2:result} = field.string{required = true}\n\t},\n\tfunction(input)\n\t\t${3:-- Your code here}\n\t\treturn {${2:result} = \"value\"}\n\tend\n}",
                "insertTextFormat": 2,
                "documentation": "Define a workflow procedure",
            },
            {
                "label": "Task",
                "kind": 3,
                "insertText": "Task \"${1:task_name}\" {\n\tentry = function()\n\t\t${2:-- Your code here}\n\tend\n}",
                "insertTextFormat": 2,
                "documentation": "Define an execution entry point",
            },
            {
                "label": "Tool",
                "kind": 3,
                "insertText": "Tool {\n\tdescription = \"${1:Tool description}\",\n\tinput = {\n\t\t${2:param} = field.string{required = true}\n\t},\n\tfunction(args)\n\t\t${3:-- Your code here}\n\t\treturn result\n\tend\n}",
                "insertTextFormat": 2,
                "documentation": "Define a tool for agents",
            },
            {
                "label": "field.string",
                "kind": 4,  # Field/Property
                "insertText": "field.string{required = ${1:true}, description = \"${2:}\"}",
                "insertTextFormat": 2,
                "documentation": "String field definition",
            },
            {
                "label": "field.number",
                "kind": 4,
                "insertText": "field.number{required = ${1:true}, default = ${2:0}}",
                "insertTextFormat": 2,
                "documentation": "Number field definition",
            },
            {
                "label": "field.boolean",
                "kind": 4,
                "insertText": "field.boolean{required = ${1:true}, default = ${2:false}}",
                "insertTextFormat": 2,
                "documentation": "Boolean field definition",
            },
            {
                "label": "field.array",
                "kind": 4,
                "insertText": "field.array{description = \"${1:}\"}",
                "insertTextFormat": 2,
                "documentation": "Array field definition",
            },
            {
                "label": "field.object",
                "kind": 4,
                "insertText": "field.object{description = \"${1:}\"}",
                "insertTextFormat": 2,
                "documentation": "Object field definition",
            },
        ]

        completions.extend(dsl_keywords)

        # Context-aware completions from registry
        if uri in self.registries:
            registry = self.registries[uri]

            # Add agent names as completions
            if hasattr(registry, 'agents'):
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
        - Hover over agent: show configuration
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
        info_parts = []

        # Show agents
        if hasattr(registry, 'agents') and registry.agents:
            info_parts.append(f"\n**Agents ({len(registry.agents)}):**")
            for agent_name, agent_decl in registry.agents.items():
                provider = getattr(agent_decl, 'provider', 'unknown')
                model = getattr(agent_decl, 'model', 'unknown')
                info_parts.append(f"- `{agent_name}`: {provider}/{model}")

        # Show parameters
        if hasattr(registry, 'parameters') and registry.parameters:
            info_parts.append(f"\n**Parameters ({len(registry.parameters)}):**")
            for param_name, param_decl in registry.parameters.items():
                param_type = getattr(param_decl, 'parameter_type', None)
                default = getattr(param_decl, 'default', None)
                type_str = param_type.value if param_type and hasattr(param_type, 'value') else 'unknown'
                default_str = f" (default: {default})" if default else ""
                info_parts.append(f"- `{param_name}`: {type_str}{default_str}")

        # Show outputs
        if hasattr(registry, 'outputs') and registry.outputs:
            info_parts.append(f"\n**Outputs ({len(registry.outputs)}):**")
            for output_name, output_decl in registry.outputs.items():
                field_type = getattr(output_decl, 'field_type', None)
                required = getattr(output_decl, 'required', False)
                type_str = field_type.value if field_type and hasattr(field_type, 'value') else 'unknown'
                req = "required" if required else "optional"
                info_parts.append(f"- `{output_name}`: {type_str} ({req})")

        if info_parts:
            return {"contents": {"kind": "markdown", "value": "\n".join(info_parts)}}

        return None

    def get_signature_help(self, uri: str, position: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Get signature help for DSL functions.

        Examples:
        - Agent{...} - show expected config fields
        - field.string{...} - show options (required, default, description)

        Args:
            uri: Document URI
            position: Cursor position {line, character}

        Returns:
            LSP signature help object or None
        """
        # Signature help for DSL functions
        signatures = [
            {
                "label": "Agent { provider, model, system_prompt, tools }",
                "documentation": "Define an LLM-powered agent",
                "parameters": [
                    {"label": "provider", "documentation": "LLM provider (openai, bedrock, google)"},
                    {"label": "model", "documentation": "Model name (gpt-4o, claude-opus-4-5, etc.)"},
                    {"label": "system_prompt", "documentation": "System prompt for the agent"},
                    {"label": "tools", "documentation": "Array of tools available to agent"},
                ],
            },
            {
                "label": "field.string { required, default, description }",
                "documentation": "String field definition",
                "parameters": [
                    {"label": "required", "documentation": "Whether field is required (boolean)"},
                    {"label": "default", "documentation": "Default value (string)"},
                    {"label": "description", "documentation": "Field description (string)"},
                ],
            },
        ]

        return {"signatures": signatures, "activeSignature": 0, "activeParameter": 0}

    def get_semantic_tokens(self, uri: str) -> Optional[Dict[str, Any]]:
        """
        Get semantic tokens for enhanced syntax highlighting.

        Provides semantic coloring based on registry information:
        - Agent/tool names colored as variables
        - Field builders colored as functions
        - Property names colored as properties

        Args:
            uri: Document URI

        Returns:
            LSP semantic tokens response or None
        """
        if uri not in self.registries or uri not in self.documents:
            return None

        registry = self.registries[uri]
        document_text = self.documents[uri]
        document_lines = document_text.split('\n')

        # Encode semantic tokens
        data = encode_semantic_tokens(registry, document_lines)

        if data is None:
            return None

        return {"data": data}

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
