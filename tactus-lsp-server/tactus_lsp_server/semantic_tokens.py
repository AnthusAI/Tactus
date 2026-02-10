"""
Semantic token encoding for Tactus LSP.

Provides semantic highlighting by analyzing the registry to identify:
- Agent declarations and references
- Tool declarations and references
- Procedure/Task keywords
- Field builders
- Configuration properties
"""

from typing import List, Any, Optional, Tuple

# Token types indices (must match order in server capabilities)
TOKEN_TYPES = ["keyword", "type", "variable", "property", "function", "parameter"]

# Token modifiers indices
TOKEN_MODIFIERS = ["declaration", "definition", "readonly"]


def _is_identifier_char(char: str) -> bool:
    return char.isalnum() or char == "_"


def encode_semantic_tokens(registry: Any, document_lines: List[str]) -> Optional[List[int]]:
    """
    Encode semantic tokens for the document.

    Returns tokens in LSP format: relative encoding where each token is 5 integers:
    [deltaLine, deltaStartChar, length, tokenType, tokenModifiers]

    Args:
        registry: ProcedureRegistry with semantic information
        document_lines: Lines of the document for position calculation

    Returns:
        Flat list of integers representing tokens, or None if no tokens
    """
    tokens: List[Tuple[int, int, int, int, int]] = []  # (line, col, length, type, mods)

    # Collect agent names and their declaration lines
    agent_names = set()
    if hasattr(registry, 'agents'):
        for agent_name in registry.agents.keys():
            agent_names.add(agent_name)

    # Collect tool names
    tool_names = set()
    if hasattr(registry, 'lua_tools'):
        for tool_name in registry.lua_tools.keys():
            tool_names.add(tool_name)

    # Scan document for semantic tokens
    for line_idx, line in enumerate(document_lines):
        # Look for agent references
        for agent_name in agent_names:
            col = 0
            while True:
                col = line.find(agent_name, col)
                if col == -1:
                    break

                # Check if it's a word boundary (not part of another identifier)
                if (col == 0 or not line[col-1].isalnum()) and \
                   (col + len(agent_name) >= len(line) or not line[col + len(agent_name)].isalnum()):
                    # Add token: variable type, possibly with declaration modifier
                    token_type = TOKEN_TYPES.index("variable")
                    token_mods = 0  # No modifiers for now (would need AST for declaration)
                    tokens.append((line_idx, col, len(agent_name), token_type, token_mods))

                col += 1

        # Look for tool references
        for tool_name in tool_names:
            col = 0
            while True:
                col = line.find(tool_name, col)
                if col == -1:
                    break

                # Check word boundary
                if (col == 0 or not line[col-1].isalnum()) and \
                   (col + len(tool_name) >= len(line) or not line[col + len(tool_name)].isalnum()):
                    # Add token: variable type
                    token_type = TOKEN_TYPES.index("variable")
                    token_mods = 0
                    tokens.append((line_idx, col, len(tool_name), token_type, token_mods))

                col += 1

        # Look for field builders (field.string, field.number, etc.)
        field_keywords = ["field.string", "field.number", "field.boolean", "field.array", "field.object"]
        for field_kw in field_keywords:
            col = 0
            while True:
                col = line.find(field_kw, col)
                if col == -1:
                    break
                before_char = line[col - 1] if col > 0 else ""
                after_index = col + len(field_kw)
                after_char = line[after_index] if after_index < len(line) else ""
                if (before_char and _is_identifier_char(before_char)) or (
                    after_char and _is_identifier_char(after_char)
                ):
                    col += 1
                    continue
                token_type = TOKEN_TYPES.index("function")
                token_mods = 0
                tokens.append((line_idx, col, len(field_kw), token_type, token_mods))
                col += 1

        # Look for property names in agent/procedure configs (provider, model, etc.)
        properties = ["provider", "model", "system_prompt", "tools", "input", "output",
                     "temperature", "max_tokens", "required", "default", "description"]
        for prop in properties:
            col = 0
            while True:
                col = line.find(prop, col)
                if col == -1:
                    break
                before_char = line[col - 1] if col > 0 else ""
                after_index = col + len(prop)
                after_char = line[after_index] if after_index < len(line) else ""
                if (before_char and _is_identifier_char(before_char)) or (
                    after_char and _is_identifier_char(after_char)
                ):
                    col += 1
                    continue

                # Check if followed by '=' after optional whitespace
                scan_index = after_index
                while scan_index < len(line) and line[scan_index].isspace():
                    scan_index += 1
                if scan_index < len(line) and line[scan_index] == "=":
                    token_type = TOKEN_TYPES.index("property")
                    token_mods = 0
                    tokens.append((line_idx, col, len(prop), token_type, token_mods))

                col += 1

    if not tokens:
        return None

    # Sort tokens by position
    tokens.sort(key=lambda t: (t[0], t[1]))

    # Encode as relative deltas
    encoded = []
    prev_line = 0
    prev_col = 0

    for line, col, length, token_type, token_mods in tokens:
        delta_line = line - prev_line
        delta_col = col if delta_line > 0 else col - prev_col

        encoded.extend([delta_line, delta_col, length, token_type, token_mods])

        prev_line = line
        prev_col = col

    return encoded


def get_token_types() -> List[str]:
    """Get the list of token types for server capabilities."""
    return TOKEN_TYPES.copy()


def get_token_modifiers() -> List[str]:
    """Get the list of token modifiers for server capabilities."""
    return TOKEN_MODIFIERS.copy()
