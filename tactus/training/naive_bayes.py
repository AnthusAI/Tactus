"""
Naive Bayes text classifier trainer.
"""

from __future__ import annotations

from pathlib import Path
from typing import List

from tactus.training.datasets import DatasetBundle
from tactus.training.types import CandidateConfig, EvalMetrics, TrainedModel


class NaiveBayesTrainer:
    name = "naive_bayes"

    def train(self, candidate: CandidateConfig, data: DatasetBundle, workdir: str) -> TrainedModel:
        try:
            from sklearn.feature_extraction.text import TfidfVectorizer
            from sklearn.naive_bayes import MultinomialNB
        except ImportError as exc:
            raise ImportError(
                "scikit-learn not installed. Install with: pip install tactus[ml]"
            ) from exc

        hyper = candidate.hyperparameters or {}
        alpha = hyper.get("alpha", 1.0)
        max_features = hyper.get("max_features", 50000)
        ngram_min = hyper.get("ngram_min", 1)
        ngram_max = hyper.get("ngram_max", 2)

        texts = [row["text"] for row in data.train]
        labels = [self._normalize_label(row["label"]) for row in data.train]

        vectorizer = TfidfVectorizer(
            max_features=max_features,
            ngram_range=(ngram_min, ngram_max),
        )
        x_train = vectorizer.fit_transform(texts)

        model = MultinomialNB(alpha=alpha)
        model.fit(x_train, labels)

        artifact_path = Path(workdir) / f"{candidate.name}.joblib"
        self._save_artifact(artifact_path, vectorizer, model)

        metrics = None
        if data.test:
            metrics = self._evaluate(vectorizer, model, data.test)

        return TrainedModel(
            artifact_path=str(artifact_path),
            backend_type="sklearn",
            backend_config={"labels": ["negative", "positive"]},
            metrics=metrics,
        )

    def _evaluate(self, vectorizer, model, test_rows: List[dict]) -> EvalMetrics:
        from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score

        x_test = vectorizer.transform([row["text"] for row in test_rows])
        y_true = [self._normalize_label(row["label"]) for row in test_rows]
        y_pred = model.predict(x_test)

        return EvalMetrics(
            accuracy=float(accuracy_score(y_true, y_pred)),
            precision=float(
                precision_score(
                    y_true, y_pred, zero_division=0, average="binary", pos_label="positive"
                )
            ),
            recall=float(
                recall_score(
                    y_true, y_pred, zero_division=0, average="binary", pos_label="positive"
                )
            ),
            f1=float(
                f1_score(y_true, y_pred, zero_division=0, average="binary", pos_label="positive")
            ),
        )

    def _normalize_label(self, label):
        if isinstance(label, str):
            return label
        if label == 0:
            return "negative"
        if label == 1:
            return "positive"
        return str(label)

    def _save_artifact(self, path: Path, vectorizer, model) -> None:
        try:
            import joblib
        except ImportError as exc:
            raise ImportError("joblib not installed. Install with: pip install tactus[ml]") from exc

        joblib.dump({"vectorizer": vectorizer, "model": model}, path)
