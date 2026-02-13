from types import SimpleNamespace

from tactus.training.datasets import DatasetBundle
from tactus.training.transformers import HFTransformersTrainer
from tactus.training.types import CandidateConfig


def test_hf_transformers_trainer_passes_training_args(monkeypatch, tmp_path):
    class FakeDataset:
        def __init__(self, rows):
            self.rows = rows

        def map(self, fn, batched=False):
            return self

    class FakeDatasets:
        @staticmethod
        def from_list(rows):
            return FakeDataset(rows)

    class FakeTokenizer:
        def __call__(self, text, truncation=None, max_length=None, padding=None):
            return {"input_ids": [1, 2, 3]}

        def save_pretrained(self, path):
            return None

    class FakeModel:
        def save_pretrained(self, path):
            return None

    captured_args = {}

    class FakeTrainingArguments:
        def __init__(self, **kwargs):
            captured_args.update(kwargs)

    class FakeTrainer:
        def __init__(self, model=None, args=None, train_dataset=None):
            self.model = model
            self.args = args
            self.train_dataset = train_dataset

        def train(self):
            return None

    fake_transformers = SimpleNamespace(
        AutoModelForSequenceClassification=SimpleNamespace(
            from_pretrained=lambda *a, **k: FakeModel()
        ),
        AutoTokenizer=SimpleNamespace(from_pretrained=lambda *a, **k: FakeTokenizer()),
        Trainer=FakeTrainer,
        TrainingArguments=FakeTrainingArguments,
    )

    monkeypatch.setitem(
        __import__("sys").modules, "datasets", SimpleNamespace(Dataset=FakeDatasets)
    )
    monkeypatch.setitem(__import__("sys").modules, "transformers", fake_transformers)

    trainer = HFTransformersTrainer()
    candidate = CandidateConfig(
        name="bert",
        trainer="hf_transformers",
        hyperparameters={
            "model": "distilbert-base-uncased",
            "epochs": 3,
            "batch_size": 16,
            "training_args": {"evaluation_strategy": "epoch"},
        },
    )

    bundle = DatasetBundle(train=[{"text": "good", "label": 1}], test=None)
    trainer.train(candidate, bundle, str(tmp_path))

    assert captured_args["num_train_epochs"] == 3
    assert captured_args["per_device_train_batch_size"] == 16
    assert captured_args["evaluation_strategy"] == "epoch"
