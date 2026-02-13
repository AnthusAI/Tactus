import sys
from types import SimpleNamespace

from tactus.training.datasets import load_dataset_bundle
from tactus.training.types import TrainingDataConfig


def test_load_dataset_bundle_local(tmp_path):
    data_file = tmp_path / "data.jsonl"
    data_file.write_text(
        "\n".join(
            [
                '{"text":"good","label":"positive"}',
                '{"text":"bad","label":"negative"}',
            ]
        )
    )

    config = TrainingDataConfig(
        source="local",
        train=str(data_file),
        test=str(data_file),
        text_field="text",
        label_field="label",
    )

    bundle = load_dataset_bundle(config)
    assert len(bundle.train) == 2
    assert bundle.test is not None
    assert bundle.train[0]["text"] == "good"


def test_load_dataset_bundle_hf(monkeypatch):
    def fake_load_dataset(name, split):
        return [
            {"text": "great", "label": 1},
            {"text": "awful", "label": 0},
        ]

    monkeypatch.setitem(
        sys.modules,
        "datasets",
        SimpleNamespace(load_dataset=fake_load_dataset),
    )

    config = TrainingDataConfig(
        source="hf",
        name="imdb",
        train="train[:2]",
        test="test[:2]",
        text_field="text",
        label_field="label",
    )

    bundle = load_dataset_bundle(config)
    assert len(bundle.train) == 2
    assert bundle.test is not None
