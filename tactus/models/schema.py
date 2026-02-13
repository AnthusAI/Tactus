"""
Schema utilities for Model primitive input/output validation.

Converts inline .tac schema declarations into Pydantic models for validation.
"""

import importlib
from typing import Any, Dict, Optional, Type

from pydantic import BaseModel, Field, create_model


def schema_dict_to_pydantic(schema_dict: Dict[str, Any], model_name: str = "Schema") -> Type[BaseModel]:
    """
    Convert an inline schema dictionary to a Pydantic model.

    Args:
        schema_dict: Schema from .tac file, e.g. { text = "string", count = "int" }
        model_name: Name for the generated Pydantic model

    Returns:
        Pydantic model class

    Example:
        >>> schema = {"text": "string", "count": "int"}
        >>> Model = schema_dict_to_pydantic(schema, "InputSchema")
        >>> instance = Model(text="hello", count=42)
        >>> instance.text
        'hello'
    """
    if not schema_dict:
        # Empty schema = no validation
        return None

    # Map Tactus type names to Python types
    type_map = {
        "string": str,
        "str": str,
        "int": int,
        "integer": int,
        "float": float,
        "number": float,
        "bool": bool,
        "boolean": bool,
        "list": list,
        "array": list,
        "dict": dict,
        "object": dict,
        "any": Any,
    }

    # Build Pydantic field definitions
    field_definitions = {}
    for field_name, field_type in schema_dict.items():
        if isinstance(field_type, str):
            # Simple type: "string", "int", etc.
            python_type = type_map.get(field_type.lower(), Any)
            field_definitions[field_name] = (python_type, ...)
        elif isinstance(field_type, dict):
            # Nested object: { nested = { field = "string" } }
            nested_model = schema_dict_to_pydantic(field_type, f"{model_name}_{field_name}")
            field_definitions[field_name] = (nested_model, ...)
        else:
            # Unknown, accept anything
            field_definitions[field_name] = (Any, ...)

    return create_model(model_name, **field_definitions)


def resolve_schema(schema_spec: Any, model_name: str = "Schema") -> Optional[Type[BaseModel]]:
    """
    Resolve a schema specification to a Pydantic model.

    Supports:
    - Inline dict: { text = "string" } -> generated Pydantic model
    - Python class reference: "myproject.schemas.MyInput" -> imported class

    Args:
        schema_spec: Schema from config (dict or string)
        model_name: Name for generated model if schema_spec is a dict

    Returns:
        Pydantic model class, or None if no schema

    Raises:
        ImportError: If Python class reference cannot be imported
        AttributeError: If Python class reference cannot be found
    """
    if not schema_spec:
        return None

    if isinstance(schema_spec, dict):
        # Inline schema
        return schema_dict_to_pydantic(schema_spec, model_name)

    if isinstance(schema_spec, str):
        # Python class reference: "package.module.ClassName"
        module_path, class_name = schema_spec.rsplit(".", 1)
        module = importlib.import_module(module_path)
        schema_class = getattr(module, class_name)

        # Verify it's a Pydantic model
        if not issubclass(schema_class, BaseModel):
            raise TypeError(
                f"Schema reference {schema_spec} must be a Pydantic BaseModel, "
                f"got {type(schema_class)}"
            )

        return schema_class

    raise TypeError(f"Schema must be dict or string, got {type(schema_spec)}")
