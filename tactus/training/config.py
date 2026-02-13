"""
Training config loader for .tac files.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from tactus.training.runner import _parse_training_config
from tactus.training.types import TrainingConfig
from tactus.validation import TactusValidator


def load_training_config(path: str, model_name: Optional[str] = None) -> TrainingConfig:
    tac_path = Path(path)
    if not tac_path.exists():
        raise FileNotFoundError(f"Training config not found: {path}")

    validator = TactusValidator()
    result = validator.validate_file(str(tac_path))
    if not result.valid:
        messages = "; ".join([e.message for e in result.errors])
        raise ValueError(f"Training config validation failed: {messages}")

    registry = result.registry
    if not registry or not registry.models:
        raise ValueError("No Model declarations found in training config")

    if model_name is None:
        if len(registry.models) != 1:
            raise ValueError("Multiple models found. Specify --model to select one.")
        model_name = next(iter(registry.models.keys()))

    if model_name not in registry.models:
        raise ValueError(f"Model not found in config: {model_name}")

    config = registry.models[model_name]
    return _parse_training_config(config, model_name=model_name)
