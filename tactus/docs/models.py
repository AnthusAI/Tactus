"""
Pydantic models for Tactus documentation structure.

These models represent the extracted documentation from .tac files,
including doc blocks, BDD specifications, and code examples.
"""

from typing import List, Optional
from pydantic import BaseModel, Field


class DocBlock(BaseModel):
    """
    A --[[doc]] comment block extracted from a .tac file.

    Contains markdown-formatted documentation text.
    """

    content: str = Field(..., description="Markdown content of the doc block")
    line_number: int = Field(..., description="Starting line number in source file")


class ParameterDoc(BaseModel):
    """
    Documentation for a single parameter extracted from --[[doc:parameter name]] blocks.
    """

    name: str = Field(..., description="Parameter name")
    description: str = Field(..., description="Parameter description")
    type_hint: Optional[str] = Field(None, description="Type hint if specified")
    required: bool = Field(True, description="Whether parameter is required")
    default: Optional[str] = Field(None, description="Default value if specified")


class BDDStep(BaseModel):
    """
    A single Given/When/Then step in a BDD scenario.
    """

    keyword: str = Field(..., description="Given, When, Then, And, But")
    text: str = Field(..., description="Step text")


class BDDScenario(BaseModel):
    """
    A BDD scenario from a Specification block.
    """

    name: str = Field(..., description="Scenario name")
    steps: List[BDDStep] = Field(default_factory=list, description="Scenario steps")
    line_number: int = Field(..., description="Starting line number")


class BDDFeature(BaseModel):
    """
    A BDD feature containing multiple scenarios.
    """

    name: str = Field(..., description="Feature name")
    description: Optional[str] = Field(None, description="Feature description")
    scenarios: List[BDDScenario] = Field(default_factory=list, description="Scenarios")
    line_number: int = Field(..., description="Starting line number")


class CodeExample(BaseModel):
    """
    A code example extracted from doc blocks or generated from BDD scenarios.
    """

    title: str = Field(..., description="Example title")
    code: str = Field(..., description="Lua code")
    description: Optional[str] = Field(None, description="Example description")
    source: str = Field(..., description="Source: 'doc_block' or 'bdd_scenario'")


class ModuleDoc(BaseModel):
    """
    Complete documentation for a Tactus module (e.g., tactus.classify).
    """

    name: str = Field(..., description="Module name (e.g., 'classify')")
    full_name: str = Field(..., description="Full module path (e.g., 'tactus.classify')")
    file_path: str = Field(..., description="Path to source .tac file")

    # Main documentation
    doc_blocks: List[DocBlock] = Field(default_factory=list, description="All doc blocks")
    overview: Optional[str] = Field(None, description="Module overview from first doc block")
    index_content: Optional[str] = Field(None, description="Content from index.md if present")

    # Parameters/Configuration
    parameters: List[ParameterDoc] = Field(default_factory=list, description="Parameter docs")

    # BDD Specifications
    features: List[BDDFeature] = Field(default_factory=list, description="BDD features")

    # Code Examples
    examples: List[CodeExample] = Field(default_factory=list, description="Code examples")

    # Metadata
    line_count: int = Field(0, description="Total lines in source file")
    has_specs: bool = Field(False, description="Whether module has BDD specs")


class DocumentationTree(BaseModel):
    """
    Tree structure representing all documentation in a directory.
    """

    root_path: str = Field(..., description="Root directory path")
    modules: List[ModuleDoc] = Field(default_factory=list, description="All documented modules")

    def get_module(self, name: str) -> Optional[ModuleDoc]:
        """Get module by name."""
        for module in self.modules:
            if module.name == name or module.full_name == name:
                return module
        return None

    def get_modules_by_prefix(self, prefix: str) -> List[ModuleDoc]:
        """Get all modules matching a prefix (e.g., 'tactus.classify')."""
        return [m for m in self.modules if m.full_name.startswith(prefix)]
