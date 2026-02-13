"""
Simple heuristics for deciding when to trigger retraining.
"""

from __future__ import annotations

from typing import Iterable


def should_trigger_retrain(metrics_history: Iterable[float], drop_threshold: float = 0.05, drift_flag: bool = False) -> bool:
    """
    Trigger retrain if accuracy drops by more than drop_threshold relative to best,
    or if drift_flag is True (from a detector).
    """
    metrics = list(metrics_history)
    if drift_flag:
        return True
    if len(metrics) < 2:
        return False
    best = max(metrics)
    latest = metrics[-1]
    if best == 0:
        return False
    return (best - latest) / best >= drop_threshold
