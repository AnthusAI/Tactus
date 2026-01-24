"""
Pydantic models for stdlib result types.

These models provide:
- Type safety and validation
- Consistent result structures across all classifiers/extractors
- Easy serialization for Lua interop
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ClassifierResult(BaseModel):
    """
    Result from any classifier (LLM, fuzzy match, etc.).

    All classifiers return this same structure, enabling polymorphism.
    """

    value: str = Field(..., description="The classification result")
    confidence: Optional[float] = Field(
        None,
        ge=0.0,
        le=1.0,
        description="Confidence score between 0.0 and 1.0",
    )
    explanation: Optional[str] = Field(
        None, description="Reasoning or explanation for the classification"
    )
    matched_text: Optional[str] = Field(
        None, description="The actual text that was matched (for fuzzy matching)"
    )
    retry_count: int = Field(0, ge=0, description="Number of retries needed to get valid result")
    raw_response: Optional[str] = Field(None, description="Raw response from LLM (if applicable)")
    error: Optional[str] = Field(None, description="Error message if classification failed")

    def to_lua_dict(self) -> Dict[str, Any]:
        """Convert to dict suitable for Lua interop."""
        return {
            "value": self.value,
            "confidence": self.confidence,
            "explanation": self.explanation,
            "matched_text": self.matched_text,
            "retry_count": self.retry_count,
            "raw_response": self.raw_response,
            "error": self.error,
        }

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict (convenience alias for to_lua_dict)."""
        return self.to_lua_dict()

    @property
    def is_error(self) -> bool:
        """Check if this result represents an error."""
        return self.error is not None or self.value == "ERROR"


class ExtractorResult(BaseModel):
    """
    Result from any extractor (LLM, schema-based, etc.).

    Contains extracted fields plus validation information.
    """

    fields: Dict[str, Any] = Field(default_factory=dict, description="Extracted field values")
    validation_errors: List[str] = Field(
        default_factory=list, description="Validation errors for extracted fields"
    )
    retry_count: int = Field(0, ge=0, description="Number of retries needed to get valid result")
    raw_response: Optional[str] = Field(None, description="Raw response from LLM (if applicable)")
    error: Optional[str] = Field(None, description="Error message if extraction failed")

    def to_lua_dict(self) -> Dict[str, Any]:
        """Convert to dict suitable for Lua interop."""
        result = dict(self.fields)  # Flatten fields to top level
        result["_validation_errors"] = self.validation_errors
        result["_retry_count"] = self.retry_count
        result["_error"] = self.error
        return result

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict (convenience alias for to_lua_dict)."""
        return self.to_lua_dict()

    @property
    def is_valid(self) -> bool:
        """Check if extraction was valid (no errors)."""
        return len(self.validation_errors) == 0 and self.error is None


class ClassifierConfig(BaseModel):
    """
    Configuration for a classifier.

    Used to validate and document classifier options.
    """

    classes: List[str] = Field(..., min_length=2, description="Valid classification values")
    target_classes: List[str] = Field(
        default_factory=list,
        description="Target classes for precision/recall metrics (subset of classes)",
    )
    prompt: Optional[str] = Field(None, description="Classification instruction/prompt")
    max_retries: int = Field(3, ge=0, description="Maximum retry attempts")
    temperature: float = Field(0.3, ge=0.0, le=2.0, description="LLM temperature")
    model: Optional[str] = Field(None, description="Model to use (optional)")
    confidence_mode: str = Field(
        "heuristic",
        description="Confidence extraction mode: 'heuristic', 'logprobs', or 'none'",
    )
    parse_direction: str = Field(
        "start",
        description="Where to look for classification: 'start', 'end', or 'any'",
    )
    method: str = Field("llm", description="Classification method: 'llm' or 'fuzzy'")

    # Fuzzy match specific
    expected: Optional[str] = Field(None, description="Expected value for fuzzy matching")
    threshold: float = Field(
        0.8, ge=0.0, le=1.0, description="Similarity threshold for fuzzy matching"
    )


class ExtractorConfig(BaseModel):
    """
    Configuration for an extractor.

    Used to validate and document extractor options.
    """

    fields: Dict[str, str] = Field(
        ..., description="Fields to extract with their types (name -> type)"
    )
    prompt: Optional[str] = Field(None, description="Extraction instruction/prompt")
    max_retries: int = Field(3, ge=0, description="Maximum retry attempts")
    temperature: float = Field(0.3, ge=0.0, le=2.0, description="LLM temperature")
    model: Optional[str] = Field(None, description="Model to use (optional)")
    strict: bool = Field(
        True, description="Whether to require all fields (strict) or allow missing"
    )
    method: str = Field("llm", description="Extraction method: 'llm' or 'schema'")


class EvaluationResult(BaseModel):
    """
    Result from evaluating a classifier/extractor on test data.

    Contains metrics like accuracy, precision, recall, F1.
    """

    accuracy: float = Field(..., ge=0.0, le=1.0)
    precision: Optional[float] = Field(None, ge=0.0, le=1.0)
    recall: Optional[float] = Field(None, ge=0.0, le=1.0)
    f1: Optional[float] = Field(None, ge=0.0, le=1.0)
    confusion_matrix: Optional[Dict[str, Dict[str, int]]] = None
    total_samples: int = Field(..., ge=0)
    total_retries: int = Field(0, ge=0)
    mean_confidence: Optional[float] = Field(None, ge=0.0, le=1.0)
    errors: List[str] = Field(default_factory=list)
