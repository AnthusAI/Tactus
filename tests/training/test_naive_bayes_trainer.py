from pathlib import Path

from tactus.training.datasets import DatasetBundle
from tactus.training.naive_bayes import NaiveBayesTrainer
from tactus.training.types import CandidateConfig


def test_naive_bayes_trainer_outputs_artifact(tmp_path):
    rows = [
        {"text": "good movie", "label": "positive"},
        {"text": "bad movie", "label": "negative"},
        {"text": "great film", "label": "positive"},
        {"text": "terrible film", "label": "negative"},
    ]
    bundle = DatasetBundle(train=rows, test=rows)

    trainer = NaiveBayesTrainer()
    candidate = CandidateConfig(name="nb", trainer="naive_bayes", hyperparameters={"alpha": 1.0})

    trained = trainer.train(candidate, bundle, str(tmp_path))

    assert trained.backend_type == "sklearn"
    assert Path(trained.artifact_path).exists()
    assert trained.metrics is not None
