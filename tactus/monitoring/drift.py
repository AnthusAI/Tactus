"""
Lightweight drift detection utilities.
"""

from __future__ import annotations

from collections import deque
from typing import Deque, Iterable


class RollingDriftDetector:
    """Detects drift based on rolling average of input lengths."""

    def __init__(self, window: int = 100, threshold_pct: float = 0.2):
        self.window = window
        self.threshold_pct = threshold_pct
        self.values: Deque[int] = deque(maxlen=window)

    def update(self, text: str) -> bool:
        length = len(text or "")
        self.values.append(length)
        if len(self.values) < self.window // 2:
            return False  # not enough data
        avg = sum(self.values) / len(self.values)
        return abs(length - avg) / (avg or 1) > self.threshold_pct


def detect_mean_shift(baseline: Iterable[float], current: Iterable[float], threshold_pct: float = 0.1) -> bool:
    base_vals = list(baseline)
    curr_vals = list(current)
    if not base_vals or not curr_vals:
        return False
    base_mean = sum(base_vals) / len(base_vals)
    curr_mean = sum(curr_vals) / len(curr_vals)
    if base_mean == 0:
        return False
    return abs(curr_mean - base_mean) / base_mean > threshold_pct
