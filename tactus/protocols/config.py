"""
Configuration models for Tactus runtime.

Defines Pydantic models for runtime configuration and procedure definitions.
"""

from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field


class TactusConfig(BaseModel):
    """
    Runtime configuration for Tactus.

    This model defines all runtime settings for a Tactus instance,
    including storage backend, HITL handler, and LLM settings.
    """

    # Storage backend
    storage_backend: str = Field(
        default="memory", description="Storage backend type: 'memory', 'file', or 'custom'"
    )
    storage_options: Dict[str, Any] = Field(
        default_factory=dict, description="Options passed to storage backend constructor"
    )

    # HITL handler
    hitl_handler: str = Field(
        default="cli", description="HITL handler type: 'cli', 'none', or 'custom'"
    )
    hitl_options: Dict[str, Any] = Field(
        default_factory=dict, description="Options passed to HITL handler constructor"
    )

    # Chat recorder
    chat_recorder: Optional[str] = Field(
        default=None, description="Chat recorder type: None, 'memory', 'file', or 'custom'"
    )
    chat_recorder_options: Dict[str, Any] = Field(
        default_factory=dict, description="Options passed to chat recorder constructor"
    )

    # LLM settings
    openai_api_key: Optional[str] = Field(default=None, description="OpenAI API key for LLM calls")
    default_model: str = Field(default="gpt-4o", description="Default LLM model to use")
    llm_temperature: float = Field(default=0.7, description="Temperature for LLM calls")

    # Execution settings
    max_iterations: int = Field(default=100, description="Maximum iterations before stopping")
    enable_checkpoints: bool = Field(
        default=True, description="Whether to enable checkpoint/resume"
    )

    # MCP server
    mcp_server_url: Optional[str] = Field(
        default=None, description="MCP server URL for tool loading"
    )
    mcp_tools: List[str] = Field(default_factory=list, description="List of MCP tools to load")


class ProcedureConfig(BaseModel):
    """
    Parsed procedure configuration from YAML.

    This model represents a validated procedure definition,
    ready for execution by the Tactus runtime.
    """

    name: str = Field(..., description="Procedure name")
    version: str = Field(..., description="Procedure version")
    description: Optional[str] = Field(None, description="Optional description")

    # Parameters (inputs)
    params: Dict[str, Any] = Field(
        default_factory=dict, description="Parameter definitions with types and defaults"
    )

    # Outputs (schema)
    outputs: Dict[str, Any] = Field(
        default_factory=dict, description="Output schema definitions with types and validation"
    )

    # Agents
    agents: Dict[str, Any] = Field(..., description="Agent definitions with prompts and tools")

    # Procedure
    procedure: str = Field(..., description="Lua procedure code")

    # HITL declarations
    hitl: Dict[str, Any] = Field(default_factory=dict, description="Pre-defined HITL interactions")

    # Sub-procedures (future)
    procedures: Dict[str, Any] = Field(
        default_factory=dict, description="Inline sub-procedure definitions (future feature)"
    )

    model_config = {"arbitrary_types_allowed": True}
