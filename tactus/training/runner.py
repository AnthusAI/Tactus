"""
Training runner for Model training configs.
"""

from __future__ import annotations

import tempfile
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Optional

from tactus.registry.local import LocalRegistry
from tactus.training.datasets import load_dataset_bundle
from tactus.training.naive_bayes import NaiveBayesTrainer
from tactus.training.transformers import HFTransformersTrainer
from tactus.training.trainers import get_trainer_registry
from tactus.training.types import CandidateConfig, TrainingConfig, TrainingDataConfig


def _register_default_trainers() -> None:
    registry = get_trainer_registry()
    registry.register(NaiveBayesTrainer())
    registry.register(HFTransformersTrainer())


def _parse_training_config(config: dict, model_name: str) -> TrainingConfig:
    data_cfg = config.get("data") or {}
    if not data_cfg:
        raise ValueError(f"Model '{model_name}' is missing required data configuration")
    data = TrainingDataConfig(
        source=data_cfg.get("source", "hf"),
        name=data_cfg.get("name"),
        train=data_cfg.get("train"),
        val=data_cfg.get("val"),
        test=data_cfg.get("test"),
        text_field=data_cfg.get("text_field", "text"),
        label_field=data_cfg.get("label_field", "label"),
    )

    candidates = []
    for candidate in config.get("candidates", []):
        candidates.append(
            CandidateConfig(
                name=candidate["name"],
                trainer=candidate["trainer"],
                hyperparameters=candidate.get("hyperparameters"),
            )
        )
    if not candidates:
        raise ValueError(f"Model '{model_name}' has no training candidates defined")

    return TrainingConfig(
        model_name=model_name,
        data=data,
        candidates=candidates,
        input=config.get("input"),
        output=config.get("output"),
    )


class TrainingRunner:
    def __init__(self, registry_dir: Optional[str] = None) -> None:
        self.registry = LocalRegistry(registry_dir=registry_dir)

    def run(
        self,
        config: TrainingConfig,
        candidate_name: Optional[str] = None,
        register: bool = True,
        evaluate: bool = True,
    ) -> dict:
        _register_default_trainers()
        trainer_registry = get_trainer_registry()

        candidates = config.candidates
        if not candidates:
            raise ValueError("No candidates defined in training config")
        if candidate_name:
            candidates = [c for c in candidates if c.name == candidate_name]
            if not candidates:
                raise ValueError(f"Candidate not found: {candidate_name}")

        data_bundle = load_dataset_bundle(config.data)
        if not evaluate:
            data_bundle = type(data_bundle)(train=data_bundle.train, val=data_bundle.val, test=None)

        results = {}
        for candidate in candidates:
            trainer = trainer_registry.get(candidate.trainer)
            with tempfile.TemporaryDirectory() as tmpdir:
                trained = trainer.train(candidate, data_bundle, tmpdir)

                metrics = trained.metrics if evaluate else None
                if register:
                    version_id = self._build_version_id(candidate.name)
                    artifact_bytes = Path(trained.artifact_path).read_bytes()
                    self.registry.register(
                        name=config.model_name,
                        version=version_id,
                        backend_type=trained.backend_type,
                        backend_config=trained.backend_config,
                        tags=["latest"],
                        metadata={
                            "candidate": candidate.name,
                            "trainer": candidate.trainer,
                            "metrics": asdict(metrics) if metrics else None,
                            "data": asdict(config.data),
                        },
                        artifact=artifact_bytes,
                        artifact_filename=Path(trained.artifact_path).name,
                    )

                results[candidate.name] = {
                    "metrics": asdict(metrics) if metrics else None,
                    "backend_type": trained.backend_type,
                }

        return results

    def _build_version_id(self, candidate_name: str) -> str:
        timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
        return f"{candidate_name}-{timestamp}"
