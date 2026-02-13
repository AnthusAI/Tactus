"""
Hugging Face sequence classifier trainer using AutoModelForSequenceClassification.
"""

from __future__ import annotations

from pathlib import Path
from typing import List

from tactus.training.datasets import DatasetBundle
from tactus.training.types import CandidateConfig, EvalMetrics, TrainedModel


class HFSequenceClassifierTrainer:
    name = "hf_sequence_classifier"

    def train(self, candidate: CandidateConfig, data: DatasetBundle, workdir: str) -> TrainedModel:
        try:
            from datasets import Dataset
            from transformers import (
                AutoModelForSequenceClassification,
                AutoTokenizer,
                Trainer,
                TrainingArguments,
            )
        except ImportError as exc:
            raise ImportError(
                "transformers not installed. Install with: pip install tactus[hf]"
            ) from exc

        hyper = candidate.hyperparameters or {}
        model_name = hyper.get("model")
        if not model_name:
            raise ValueError("hf_sequence_classifier trainer requires hyperparameters.model")

        label_list = hyper.get("labels", ["negative", "positive"])
        id2label = {i: label for i, label in enumerate(label_list)}
        label2id = {label: i for i, label in enumerate(label_list)}

        tokenizer = AutoTokenizer.from_pretrained(model_name)
        model = AutoModelForSequenceClassification.from_pretrained(
            model_name,
            num_labels=len(label_list),
            id2label=id2label,
            label2id=label2id,
        )

        train_dataset = Dataset.from_list(self._normalize_rows(data.train, label2id))
        test_dataset = (
            Dataset.from_list(self._normalize_rows(data.test, label2id)) if data.test else None
        )

        max_length = hyper.get("max_length")
        padding = hyper.get("padding")
        truncation = hyper.get("truncation", True)

        def tokenize(batch):
            return tokenizer(
                batch["text"],
                truncation=truncation,
                max_length=max_length,
                padding=padding,
            )

        train_dataset = train_dataset.map(tokenize, batched=True)
        if test_dataset:
            test_dataset = test_dataset.map(tokenize, batched=True)

        args = TrainingArguments(**self._build_training_args(hyper, workdir))

        trainer = Trainer(model=model, args=args, train_dataset=train_dataset)
        trainer.train()

        artifact_path = Path(workdir) / f"{candidate.name}"
        model.save_pretrained(artifact_path)
        tokenizer.save_pretrained(artifact_path)

        metrics = None
        if test_dataset:
            metrics = self._evaluate(trainer, test_dataset)

        return TrainedModel(
            artifact_path=str(artifact_path),
            backend_type="hf_sequence_classifier",
            backend_config={"model": str(artifact_path)},
            metrics=metrics,
        )

    def _normalize_rows(self, rows: List[dict], label2id: dict) -> List[dict]:
        normalized = []
        for row in rows:
            label = row["label"]
            if isinstance(label, str):
                label = label2id.get(label, label)
            normalized.append({"text": row["text"], "labels": label})
        return normalized

    def _evaluate(self, trainer, dataset) -> EvalMetrics:
        try:
            from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score
        except ImportError as exc:
            raise ImportError(
                "scikit-learn not installed. Install with: pip install tactus[ml]"
            ) from exc

        preds = trainer.predict(dataset)
        y_pred = preds.predictions.argmax(axis=-1)
        y_true = preds.label_ids

        return EvalMetrics(
            accuracy=float(accuracy_score(y_true, y_pred)),
            precision=float(precision_score(y_true, y_pred, zero_division=0, average="binary")),
            recall=float(recall_score(y_true, y_pred, zero_division=0, average="binary")),
            f1=float(f1_score(y_true, y_pred, zero_division=0, average="binary")),
        )

    def _build_training_args(self, hyper: dict, workdir: str) -> dict:
        base_args = {
            "output_dir": str(Path(workdir) / "hf_output"),
            "per_device_train_batch_size": hyper.get("batch_size", 8),
            "num_train_epochs": hyper.get("epochs", 1),
            "learning_rate": hyper.get("learning_rate", 2e-5),
            "logging_steps": hyper.get("logging_steps", 10),
            "save_strategy": hyper.get("save_strategy", "no"),
            "evaluation_strategy": hyper.get("evaluation_strategy", "no"),
            "weight_decay": hyper.get("weight_decay", 0.0),
            "warmup_steps": hyper.get("warmup_steps", 0),
            "gradient_accumulation_steps": hyper.get("gradient_accumulation_steps", 1),
            "seed": hyper.get("seed"),
        }
        training_args = hyper.get("training_args") or {}
        base_args.update(training_args)
        if "evaluation_strategy" in base_args and "eval_strategy" not in base_args:
            base_args["eval_strategy"] = base_args["evaluation_strategy"]
        if "evaluation_strategy" in base_args and "eval_strategy" in base_args:
            base_args.pop("evaluation_strategy", None)
        return {k: v for k, v in base_args.items() if v is not None}
