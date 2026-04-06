"""
Dataset loading utilities for training.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from importlib import import_module
from pathlib import Path
from typing import Iterable, List, Optional

from tactus.training.types import TrainingDataConfig


@dataclass
class DatasetBundle:
    train: List[dict]
    val: Optional[List[dict]] = None
    test: Optional[List[dict]] = None


def _load_jsonl(path: str) -> List[dict]:
    records = []
    for line in Path(path).read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        records.append(json.loads(line))
    return records


def _select_fields(records: Iterable[dict], text_field: str, label_field: str) -> List[dict]:
    selected = []
    for record in records:
        selected.append(
            {
                "text": record.get(text_field),
                "label": record.get(label_field),
            }
        )
    return selected


def _resolve_split_value(value, split: str):
    if isinstance(value, dict):
        return value.get(split)
    return value


def _apply_sampling(records, shuffle: Optional[bool], limit: Optional[int], seed: Optional[int]):
    if records is None:
        return None

    if shuffle and hasattr(records, "shuffle"):
        records = records.shuffle(seed=seed)
    if limit is not None and hasattr(records, "select"):
        return records.select(range(limit))

    if not isinstance(records, list):
        records = list(records)

    if shuffle:
        import random

        rng = random.Random(seed)
        rng.shuffle(records)

    if limit is not None:
        records = records[:limit]

    return records


def load_dataset_bundle(config: TrainingDataConfig) -> DatasetBundle:
    if config.source == "hf":
        try:
            load_dataset = import_module("datasets").load_dataset
        except ImportError as exc:
            raise ImportError(
                "datasets not installed. Install with: pip install tactus[ml]"
            ) from exc

        if not config.name:
            raise ValueError("HF dataset name is required for source='hf'")
        if not config.train:
            raise ValueError("HF train split is required")

        train_records = load_dataset(config.name, split=config.train)
        train_records = _apply_sampling(
            train_records,
            _resolve_split_value(config.shuffle, "train"),
            _resolve_split_value(config.limit, "train"),
            config.seed,
        )
        train = _select_fields(train_records, config.text_field, config.label_field)

        val = None
        if config.val:
            val_records = load_dataset(config.name, split=config.val)
            val_records = _apply_sampling(
                val_records,
                _resolve_split_value(config.shuffle, "val"),
                _resolve_split_value(config.limit, "val"),
                config.seed,
            )
            val = _select_fields(val_records, config.text_field, config.label_field)

        test = None
        if config.test:
            test_records = load_dataset(config.name, split=config.test)
            test_records = _apply_sampling(
                test_records,
                _resolve_split_value(config.shuffle, "test"),
                _resolve_split_value(config.limit, "test"),
                config.seed,
            )
            test = _select_fields(test_records, config.text_field, config.label_field)

        return DatasetBundle(train=train, val=val, test=test)

    if config.source == "local":
        if not config.train:
            raise ValueError("Local dataset requires a train path")

        train_records = _apply_sampling(
            _load_jsonl(config.train),
            _resolve_split_value(config.shuffle, "train"),
            _resolve_split_value(config.limit, "train"),
            config.seed,
        )
        train = _select_fields(train_records, config.text_field, config.label_field)
        val = (
            _select_fields(
                _apply_sampling(
                    _load_jsonl(config.val),
                    _resolve_split_value(config.shuffle, "val"),
                    _resolve_split_value(config.limit, "val"),
                    config.seed,
                ),
                config.text_field,
                config.label_field,
            )
            if config.val
            else None
        )
        test = (
            _select_fields(
                _apply_sampling(
                    _load_jsonl(config.test),
                    _resolve_split_value(config.shuffle, "test"),
                    _resolve_split_value(config.limit, "test"),
                    config.seed,
                ),
                config.text_field,
                config.label_field,
            )
            if config.test
            else None
        )
        return DatasetBundle(train=train, val=val, test=test)

    raise ValueError(f"Unknown data source: {config.source}")
