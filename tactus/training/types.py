"""
Types for training and evaluation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class TrainingDataConfig:
    source: str  # "hf" or "local"
    name: Optional[str] = None  # HF dataset name
    train: Optional[str] = None  # split or file path
    val: Optional[str] = None
    test: Optional[str] = None
    text_field: str = "text"
    label_field: str = "label"


@dataclass
class CandidateConfig:
    name: str
    trainer: str
    hyperparameters: Optional[Dict[str, Any]] = None


@dataclass
class TrainingConfig:
    model_name: str
    data: TrainingDataConfig
    candidates: List[CandidateConfig]
    input: Optional[Dict[str, Any]] = None
    output: Optional[Dict[str, Any]] = None


@dataclass
class EvalMetrics:
    accuracy: float
    precision: float
    recall: float
    f1: float


@dataclass
class TrainedModel:
    artifact_path: str
    backend_type: str
    backend_config: Dict[str, Any]
    metrics: Optional[EvalMetrics] = None
