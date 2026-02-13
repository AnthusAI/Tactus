"""
Training and evaluation runners.
"""

from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, List, Optional

from tactus.training.types import CandidateConfig, EvalMetrics, TrainingConfig


class TrainingRunner:
    """Execute training scripts for candidates."""

    def __init__(self, workdir: Optional[str] = None):
        self.workdir = workdir

    def run_candidate(self, candidate: CandidateConfig, config: TrainingConfig) -> Dict:
        """
        Run a candidate's training script as a subprocess.
        Expects script to emit JSON metrics to stdout or write metrics.json in cwd.
        """
        script = candidate.training.get("script")
        if script is None:
            raise ValueError(f"Candidate {candidate.name} missing training.script")

        # Prepare env/args
        args = ["python3", script]
        for key, value in (candidate.training.get("args") or {}).items():
            args.append(f"--{key}")
            args.append(str(value))

        proc = subprocess.run(
            args,
            cwd=self.workdir,
            capture_output=True,
            text=True,
            check=False,
        )

        if proc.returncode != 0:
            raise RuntimeError(f"Training failed for {candidate.name}: {proc.stderr}")

        # Try stdout first
        stdout = proc.stdout.strip()
        if stdout:
            try:
                return json.loads(stdout)
            except json.JSONDecodeError:
                pass

        # Fallback to metrics.json if present
        metrics_path = Path(self.workdir or ".") / "metrics.json"
        if metrics_path.exists():
            return json.loads(metrics_path.read_text())

        return {}


class EvaluationRunner:
    """Compute evaluation metrics given predictions and labels."""

    @staticmethod
    def evaluate(predictions: List[str], labels: List[str]) -> EvalMetrics:
        if len(predictions) != len(labels):
            raise ValueError("Predictions and labels length mismatch")

        tp = fp = fn = tn = 0
        for pred, label in zip(predictions, labels):
            if pred == "positive":
                if label == "positive":
                    tp += 1
                else:
                    fp += 1
            else:
                if label == "positive":
                    fn += 1
                else:
                    tn += 1

        total = len(predictions)
        accuracy = (tp + tn) / total if total else 0.0
        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = (2 * precision * recall) / (precision + recall) if (precision + recall) else 0.0

        return EvalMetrics(
            accuracy=accuracy,
            precision=precision,
            recall=recall,
            f1=f1,
        )
