"""
Sklearn model backend for inference.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, List, Optional


class SklearnModelBackend:
    def __init__(self, path: str, labels: Optional[List[str]] = None):
        self.path = Path(path)
        self.labels = labels or []
        self._artifact = None

    def _load(self) -> None:
        if self._artifact is not None:
            return
        try:
            import joblib
        except ImportError as exc:
            raise ImportError("joblib not installed. Install with: pip install tactus[ml]") from exc

        if not self.path.exists():
            raise FileNotFoundError(f"Model file not found: {self.path}")
        self._artifact = joblib.load(self.path)

    async def predict(self, input_data: Any) -> Any:
        return self.predict_sync(input_data)

    def predict_sync(self, input_data: Any) -> Any:
        self._load()

        text = input_data
        if isinstance(input_data, dict):
            text = input_data.get("text") or input_data.get("input") or input_data

        vectorizer = self._artifact["vectorizer"]
        model = self._artifact["model"]

        x = vectorizer.transform([text])
        pred = model.predict(x)[0]

        confidence = None
        if hasattr(model, "predict_proba"):
            probs = model.predict_proba(x)[0]
            confidence = float(max(probs))

        label = pred
        if self.labels:
            try:
                index = int(pred)
                if 0 <= index < len(self.labels):
                    label = self.labels[index]
            except (TypeError, ValueError):
                label = pred

        return {"label": label, "confidence": confidence}
