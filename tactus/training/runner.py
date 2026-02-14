"""
Training runner for Model training configs.
"""

from __future__ import annotations

import shutil
import tempfile
import time
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Optional
from collections import Counter

from tactus.registry.local import LocalRegistry
from tactus.training.datasets import DatasetBundle, load_dataset_bundle
from tactus.training.naive_bayes import NaiveBayesTrainer
from tactus.training.sequence_classifier import HFSequenceClassifierTrainer
from tactus.training.trainers import get_trainer_registry
from tactus.training.types import CandidateConfig, TrainingConfig, TrainingDataConfig


def _register_default_trainers() -> None:
    registry = get_trainer_registry()
    registry.register(NaiveBayesTrainer())
    registry.register(HFSequenceClassifierTrainer())


def _parse_training_config(config: dict, model_name: str) -> TrainingConfig:
    training_cfg = config.get("training")
    if not training_cfg:
        raise ValueError(
            f"Model '{model_name}' missing training block (required for training)."
        )

    data_cfg = training_cfg.get("data") or {}
    if not data_cfg:
        raise ValueError(
            f"Model '{model_name}' training block is missing required data configuration."
        )
    data = TrainingDataConfig(
        source=data_cfg.get("source", "hf"),
        name=data_cfg.get("name"),
        train=data_cfg.get("train"),
        val=data_cfg.get("val"),
        test=data_cfg.get("test"),
        text_field=data_cfg.get("text_field", "text"),
        label_field=data_cfg.get("label_field", "label"),
        shuffle=data_cfg.get("shuffle"),
        limit=data_cfg.get("limit"),
        seed=data_cfg.get("seed"),
    )

    candidates = []
    for candidate in training_cfg.get("candidates", []):
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
        data_summary = self._summarize_data(data_bundle)
        if not evaluate:
            data_bundle = type(data_bundle)(train=data_bundle.train, val=data_bundle.val, test=None)

        results = {}
        for candidate in candidates:
            trainer = trainer_registry.get(candidate.trainer)
            with tempfile.TemporaryDirectory() as tmpdir:
                start_time = time.perf_counter()
                trained = trainer.train(candidate, data_bundle, tmpdir)
                duration = time.perf_counter() - start_time

                metrics = trained.metrics if evaluate else None
                if register:
                    version_id = self._build_version_id(candidate.name)
                    artifact_path = Path(trained.artifact_path)
                    if artifact_path.is_dir():
                        archive_root = Path(tmpdir) / artifact_path.name
                        archive_path = Path(
                            shutil.make_archive(str(archive_root), "zip", root_dir=artifact_path)
                        )
                        artifact_bytes = archive_path.read_bytes()
                        artifact_filename = archive_path.name
                    else:
                        artifact_bytes = artifact_path.read_bytes()
                        artifact_filename = artifact_path.name
                    self.registry.register(
                        name=config.model_name,
                        version=version_id,
                        backend_type=trained.backend_type,
                        backend_config=trained.backend_config,
                        tags=["latest", f"candidate/{candidate.name}"],
                        metadata={
                            "candidate": candidate.name,
                            "trainer": candidate.trainer,
                            "metrics": asdict(metrics) if metrics else None,
                            "data": asdict(config.data),
                        },
                        artifact=artifact_bytes,
                        artifact_filename=artifact_filename,
                    )

                results[candidate.name] = {
                    "metrics": asdict(metrics) if metrics else None,
                    "backend_type": trained.backend_type,
                    "hyperparameters": candidate.hyperparameters or {},
                    "data": data_summary,
                    "duration_seconds": round(duration, 3),
                }

        return results

    def _build_version_id(self, candidate_name: str) -> str:
        timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
        return f"{candidate_name}-{timestamp}"

    def _summarize_data(self, bundle: DatasetBundle) -> dict:
        def summarize_split(rows):
            if not rows:
                return {"count": 0, "labels": {}}
            labels = Counter(str(row.get("label")) for row in rows)
            return {"count": len(rows), "labels": dict(labels)}

        return {
            "train": summarize_split(bundle.train),
            "val": summarize_split(bundle.val),
            "test": summarize_split(bundle.test),
        }
