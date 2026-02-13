"""
Trainer interfaces and registry.
"""

from __future__ import annotations

from typing import Dict, Protocol

from tactus.training.datasets import DatasetBundle
from tactus.training.types import CandidateConfig, TrainedModel


class Trainer(Protocol):
    name: str

    def train(
        self, candidate: CandidateConfig, data: DatasetBundle, workdir: str
    ) -> TrainedModel: ...


class TrainerRegistry:
    def __init__(self) -> None:
        self._trainers: Dict[str, Trainer] = {}

    def register(self, trainer: Trainer) -> None:
        self._trainers[trainer.name] = trainer

    def get(self, name: str) -> Trainer:
        if name not in self._trainers:
            raise ValueError(f"Unknown trainer: {name}")
        return self._trainers[name]


_REGISTRY = TrainerRegistry()


def get_trainer_registry() -> TrainerRegistry:
    return _REGISTRY
