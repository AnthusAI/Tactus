"""
Types for training and evaluation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class CandidateConfig:
    name: str
    type: str
    training: Dict[str, Any]
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class TrainingConfig:
    model_name: str
    train: str
    val: Optional[str] = None
    test: Optional[str] = None
    candidates: Optional[List[CandidateConfig]] = None
    hyperparameters: Optional[Dict[str, Any]] = None


@dataclass
class EvalMetrics:
    accuracy: float
    precision: float
    recall: float
    f1: float
    latency_ms: Optional[float] = None
    cost_per_pred: Optional[float] = None
