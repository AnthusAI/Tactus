"""
Hugging Face sequence classifier backend using AutoModelForSequenceClassification.
"""

from __future__ import annotations

from typing import Any, Optional


class HFSequenceClassifierBackend:
    def __init__(
        self,
        model: str,
        revision: Optional[str] = None,
        device: Optional[str] = None,
    ):
        self.model_name = model
        self.revision = revision
        self.device = device
        self._tokenizer = None
        self._model = None

    def _load(self) -> None:
        if self._model is not None:
            return
        try:
            from transformers import AutoModelForSequenceClassification, AutoTokenizer
        except ImportError as exc:
            raise ImportError(
                "transformers not installed. Install with: pip install tactus[hf]"
            ) from exc

        self._tokenizer = AutoTokenizer.from_pretrained(self.model_name, revision=self.revision)
        self._model = AutoModelForSequenceClassification.from_pretrained(
            self.model_name, revision=self.revision
        )
        if self.device:
            self._model.to(self.device)

    async def predict(self, input_data: Any) -> Any:
        return self.predict_sync(input_data)

    def predict_sync(self, input_data: Any) -> Any:
        self._load()
        try:
            import torch
        except ImportError as exc:
            raise ImportError("torch not installed. Install with: pip install tactus[hf]") from exc

        text = input_data
        if isinstance(input_data, dict):
            text = input_data.get("text") or input_data.get("input") or input_data

        inputs = self._tokenizer(text, return_tensors="pt", truncation=True)
        if self.device:
            inputs = {k: v.to(self.device) for k, v in inputs.items()}

        with torch.no_grad():
            outputs = self._model(**inputs)

        logits = outputs.logits
        probs = torch.softmax(logits, dim=-1)[0]
        score, idx = torch.max(probs, dim=-1)

        label = self._model.config.id2label.get(int(idx), str(int(idx)))
        return {"label": label, "confidence": float(score)}
